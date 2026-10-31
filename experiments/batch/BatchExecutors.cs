using System.Diagnostics;
using System.Net.Sockets;
using BoundedAgents.Models;
using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Oracle;
using BoundedAgents.Shared.Tokenizer;

namespace BoundedAgents.Experiments.Batch;

/// <summary>Model access. Production: Azure OpenAI, SDK retries off; a 429 is <see cref="LlmRateLimitedException"/>.</summary>
public interface ILlmCaller
{
    Task<LlmCallDetail> CallAsync(string systemPrompt, string userPrompt, string deployment);
}

public sealed class AzureLlmCaller(string endpoint) : ILlmCaller
{
    public Task<LlmCallDetail> CallAsync(string systemPrompt, string userPrompt, string deployment) =>
        LlmClient.CallAzureOpenAiDetailedAsync(systemPrompt, userPrompt, deployment, endpoint);
}

/// <summary>
/// Runs one event up to and after the model call. <c>callModel(observationText, userPrompt)</c>
/// is the runner's gate (hash check, journal, budget, the call itself).
/// </summary>
public interface IBatchExecutor : IAsyncDisposable
{
    Task<GroundingRecord> ExecuteAsync(PlanEvent e, string deployment, Func<string, string, Task<LlmResponse>> callModel);

    /// <summary>
    /// Zero-LLM: rebuild the event's observation and score a stored locator against the live DOM
    /// exactly as the paid path does (same observation, locator parse, oracle evaluation).
    /// </summary>
    Task<BatchScore> RescoreAsync(PlanEvent e, string locatorRaw);
}

/// <summary>
/// Production executor: own python http.server on the Config port (pipes drained), restarted per
/// cell as in the corpus runs, and GroundingRunner.RunOneStagedAsync (the RunOneAsync pipeline).
/// Refuses if the port already answers before its own server starts (a foreign server could
/// serve other bytes), and waits until the page answers 200 before use.
/// </summary>
public sealed class PlaywrightBatchExecutor : IBatchExecutor
{
    private readonly string _repoRoot;
    private readonly string _baseUrl;
    private readonly int _port;
    private readonly int _seed;
    private readonly Dictionary<string, TruthFile> _truth = new(StringComparer.Ordinal);
    private Process? _server;
    private (string Page, string Bundle, string Encoding, string Model, int Rep)? _cell;
    private Microsoft.Playwright.IPlaywright? _rsPlaywright;
    private Microsoft.Playwright.IBrowser? _rsBrowser;
    private Microsoft.Playwright.IPage? _rsPage;
    private (string Page, string Bundle, string Encoding)? _rsCell;
    private (string Sha, int Tokens, IReadOnlyList<ElementData> Raw)? _rsObs;
    private static readonly HttpClient Http = new() { Timeout = TimeSpan.FromSeconds(5) };

    public PlaywrightBatchExecutor(string repoRoot, string? baseUrl = null)
    {
        _repoRoot = repoRoot;
        _baseUrl = (baseUrl ?? Config.TestbedBaseUrl).TrimEnd('/');
        _port = new Uri(_baseUrl).Port;
        _seed = Config.RandomSeed;
        if (PortAnswers(_port))
        {
            throw new BatchRefusedException(
                $"port {_port} is already in use — refusing to read observations from a server this runner did not start");
        }
    }

    public async Task<GroundingRecord> ExecuteAsync(
        PlanEvent e, string deployment, Func<string, string, Task<LlmResponse>> callModel)
    {
        var cell = (e.Page, e.Bundle, e.Encoding, e.Model, e.Rep);
        if (_server is null || _cell != cell)
        {
            await RestartServerAsync(e.Page);
            _cell = cell;
        }
        if (!_truth.TryGetValue(e.Page, out var truth))
        {
            truth = BatchPreflight.LoadTruth(_repoRoot, e.Page);
            _truth[e.Page] = truth;
        }
        var t = truth.Targets.Single(x => x.Id == e.TaskId);
        var volIds = new HashSet<string>(truth.VolatilityLabels.VolatileIds, StringComparer.Ordinal);
        var volCls = new HashSet<string>(truth.VolatilityLabels.VolatileClasses, StringComparer.Ordinal);

        Task<GroundingRecord> Run() => GroundingRunner.RunOneStagedAsync(
            taskId: t.Id,
            taskDescription: t.Intent,
            oracleRef: new OracleRef(t.Oracle),
            pagePath: $"pages/{e.Page}.html",
            bundle: e.Bundle,
            encoding: e.Encoding,
            regime: "full_page",
            model: deployment,
            repetition: e.Repetition,
            callModel: callModel,
            expectedStableSignal: t.ExpectedStableSignal,
            volatileIds: volIds,
            volatileClasses: volCls,
            signalAttrs: t.SignalAttrs,
            seed: _seed,
            baseUrl: _baseUrl);

        try
        {
            return await Run();
        }
        catch (TimeoutException)
        {
            // Safe to repeat: a response already journaled is replayed, never bought again.
            Console.Error.WriteLine($"  [server timeout — restarting and repeating {e.Key}]");
            await RestartServerAsync(e.Page);
            return await Run();
        }
    }

    public async Task<BatchScore> RescoreAsync(PlanEvent e, string locatorRaw)
    {
        if (_server is null)
        {
            await RestartServerAsync(e.Page);
        }
        var truth = TruthOf(e.Page);
        var t = truth.Targets.Single(x => x.Id == e.TaskId);
        var volIds = new HashSet<string>(truth.VolatilityLabels.VolatileIds, StringComparer.Ordinal);
        var volCls = new HashSet<string>(truth.VolatilityLabels.VolatileClasses, StringComparer.Ordinal);

        var cell = (e.Page, e.Bundle, e.Encoding);
        if (_rsCell != cell || _rsPage is null || _rsObs is null)
        {
            _rsPlaywright ??= await Microsoft.Playwright.Playwright.CreateAsync();
            _rsBrowser ??= await _rsPlaywright.Chromium.LaunchAsync(new() { Headless = true });
            if (_rsPage is not null)
            {
                await _rsPage.CloseAsync();
            }
            _rsPage = await _rsBrowser.NewPageAsync();
            await _rsPage.GotoAsync($"{_baseUrl}/pages/{e.Page}.html", new() { Timeout = 90_000 });
            await _rsPage.WaitForLoadStateAsync(Microsoft.Playwright.LoadState.NetworkIdle, new() { Timeout = 90_000 });
            var (obsText, raw, _) = await Observation.BuildObservationAsync(_rsPage, e.Bundle, e.Encoding, volIds, volCls);
            _rsObs = (Hashing.Sha256Hex(obsText), TokenCounter.CountTokens(obsText), raw);
            _rsCell = cell;
        }

        // Same calls, in the same order, as GroundingRunner.RunOneStagedAsync after the model call.
        var bundleSet = AttributeBundles.ResolveBundleSetForSignalCheck(e.Bundle);
        var (locatorType, locatorValue) = GroundingRunner.ParseLocatorForReplay(locatorRaw);
        var oracleRef = new OracleRef(t.Oracle);
        var oracleEl = await Oracle.FindOracleElementAsync(_rsPage, oracleRef);
        var ev = await Oracle.EvaluateLocatorAsync(
            _rsPage, locatorType, locatorValue, oracleEl,
            _rsObs.Value.Raw, oracleRef.OracleId, attr => bundleSet.Contains(attr),
            t.ExpectedStableSignal, volIds, volCls, t.SignalAttrs);
        return new BatchScore(_rsObs.Value.Sha, _rsObs.Value.Tokens, locatorType, locatorValue, ev.Success,
            ev.FailureMode, ev.PredicateUniqueMatch, ev.PredicateMatchesOracle, ev.PredicateNonVolatile,
            ev.PredicateNonPositional, ev.StableSignalPresentInBundle);
    }

    private TruthFile TruthOf(string page)
    {
        if (!_truth.TryGetValue(page, out var truth))
        {
            truth = BatchPreflight.LoadTruth(_repoRoot, page);
            _truth[page] = truth;
        }
        return truth;
    }

    /// <summary>Zero-LLM: build one observation exactly as the paid path does.</summary>
    public async Task<string> BuildObservationAsync(string page, string bundle, string encoding)
    {
        if (_server is null)
        {
            await RestartServerAsync(page);
        }
        if (!_truth.TryGetValue(page, out var truth))
        {
            truth = BatchPreflight.LoadTruth(_repoRoot, page);
            _truth[page] = truth;
        }
        var volIds = new HashSet<string>(truth.VolatilityLabels.VolatileIds, StringComparer.Ordinal);
        var volCls = new HashSet<string>(truth.VolatilityLabels.VolatileClasses, StringComparer.Ordinal);
        using var playwright = await Microsoft.Playwright.Playwright.CreateAsync();
        var browser = await playwright.Chromium.LaunchAsync(new() { Headless = true });
        try
        {
            var p = await browser.NewPageAsync();
            await p.GotoAsync($"{_baseUrl}/pages/{page}.html", new() { Timeout = 90_000 });
            await p.WaitForLoadStateAsync(Microsoft.Playwright.LoadState.NetworkIdle, new() { Timeout = 90_000 });
            return (await Observation.BuildObservationAsync(p, bundle, encoding, volIds, volCls)).ObsText;
        }
        finally
        {
            await browser.CloseAsync();
        }
    }

    private async Task RestartServerAsync(string page)
    {
        await StopServerAsync();
        var testbedDir = Path.Combine(_repoRoot, "shared", "testbed");
        var srv = Process.Start(new ProcessStartInfo
        {
            FileName = "python",
            Arguments = $"-m http.server {_port} --directory \"{testbedDir}\"",
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        })!;
        srv.BeginOutputReadLine();   // drain: an unread pipe blocks http.server
        srv.BeginErrorReadLine();
        _server = srv;

        var url = $"{_baseUrl}/pages/{page}.html";
        var deadline = DateTime.UtcNow.AddSeconds(15);
        while (true)
        {
            if (srv.HasExited)
            {
                throw new BatchRefusedException($"http.server on port {_port} exited (code {srv.ExitCode})");
            }
            try
            {
                using var resp = await Http.GetAsync(url);
                if (resp.IsSuccessStatusCode)
                {
                    return;
                }
            }
            catch (HttpRequestException) { }
            catch (TaskCanceledException) { }
            if (DateTime.UtcNow > deadline)
            {
                throw new BatchRefusedException($"http.server did not serve {url} within 15 s");
            }
            await Task.Delay(200);
        }
    }

    private async Task StopServerAsync()
    {
        if (_server is null)
        {
            return;
        }
        try { _server.Kill(entireProcessTree: true); } catch { }
        try { await _server.WaitForExitAsync(); } catch { }
        _server.Dispose();
        _server = null;
        await Task.Delay(300);
    }

    private static bool PortAnswers(int port)
    {
        try
        {
            using var c = new TcpClient();
            return c.ConnectAsync("127.0.0.1", port).Wait(TimeSpan.FromMilliseconds(500)) && c.Connected;
        }
        catch
        {
            return false;
        }
    }

    public async ValueTask DisposeAsync()
    {
        if (_rsBrowser is not null)
        {
            try { await _rsBrowser.CloseAsync(); } catch { }
        }
        _rsPlaywright?.Dispose();
        await StopServerAsync();
    }
}
