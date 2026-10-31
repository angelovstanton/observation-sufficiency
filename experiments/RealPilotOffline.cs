using System.Security.Cryptography;
using System.Text.Json;
using System.Text.RegularExpressions;
using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Oracle;
using Microsoft.Playwright;

namespace BoundedAgents.Experiments;

/// <summary>
/// Offline page load of the real-site pilot (pilot_rule.md §2 (б)), shared by the adapter
/// (experiments/modes/RealPilotMode.cs) and the experiments/batch pilot profile (linked there, nothing else is).
/// A cached, decoded HTML document is fulfilled for the first main-frame navigation; every other
/// request is aborted, WebSockets are not connected, service workers blocked, no host name resolves.
/// No model client and no network request lives here.
/// </summary>
internal static class RealPilotOffline
{
    public sealed class LoadStats { public int Fulfilled; public int Aborted; public int WebSockets; public int WsFramesReceived; }

    public static Task<IBrowser> LaunchAsync(IPlaywright playwright) =>
        playwright.Chromium.LaunchAsync(new()
        {
            Headless = true,
            Args = new[] { "--host-resolver-rules=MAP * ~NOTFOUND" },
            // Nothing listens on 127.0.0.1:9: any connection that escapes the route (WebSockets,
            // IP-literal hosts) fails. Requests are fulfilled/aborted by the route before this.
            Proxy = new Proxy { Server = "http://127.0.0.1:9", Bypass = "<-loopback>" },
        });

    public static async Task<(IBrowserContext Ctx, IPage Page, LoadStats Stats)> LoadAsync(
        IBrowser browser, string url, byte[] body, DateTime? fixedTime, string? shimJs)
    {
        var ctx = await browser.NewContextAsync(new() { ServiceWorkers = ServiceWorkerPolicy.Block });
        var stats = new LoadStats();
        if (shimJs is not null)
        {
            await ctx.Clock.SetFixedTimeAsync(fixedTime ?? throw new InvalidOperationException("shims need a timestamp"));
            await ctx.AddInitScriptAsync(shimJs);
        }
        var page = await ctx.NewPageAsync();
        // WebSockets: counted; they cannot connect (proxy + resolver above). RouteWebSocketAsync is not
        // used: in Microsoft.Playwright 1.60 its message dispatch throws an unhandled KeyNotFoundException.
        page.WebSocket += (_, ws) =>
        {
            Interlocked.Increment(ref stats.WebSockets);
            ws.FrameReceived += (_, _) => Interlocked.Increment(ref stats.WsFramesReceived);
        };
        await ctx.RouteAsync(new Regex(".*"), async route =>
        {
            var req = route.Request;
            if (req.IsNavigationRequest && req.Frame == page.MainFrame
                && Interlocked.CompareExchange(ref stats.Fulfilled, 1, 0) == 0)
            {
                await route.FulfillAsync(new()
                {
                    Status = 200, ContentType = "text/html; charset=utf-8", BodyBytes = body,
                });
                return;
            }
            Interlocked.Increment(ref stats.Aborted);
            await route.AbortAsync();
        });
        // Readiness wait identical to the corpus dump modes.
        await page.GotoAsync(url, new() { Timeout = 90_000 });
        await page.WaitForLoadStateAsync(LoadState.NetworkIdle, new() { Timeout = 90_000 });
        return (ctx, page, stats);
    }

    /// <summary>Sets data-oracle-id = id on the element each XPath selects; returns how many were set.</summary>
    public static Task<int> SetMarkersAsync(IPage page, IEnumerable<(string Id, string Xpath)> markers) =>
        page.EvaluateAsync<int>(@"(ms) => {
                        let n = 0;
                        for (const m of ms) {
                          const el = document.evaluate(m.xpath, document, null,
                            XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                          if (el) { el.setAttribute('data-oracle-id', m.id); n++; }
                        }
                        return n;
                      }", markers.Select(m => new { id = m.Id, xpath = m.Xpath }).ToArray());

    /// <summary>
    /// The pilot's observation of one cell (pilot_rule.md addendum 2026-10-13): a fresh offline load,
    /// every marker of the site set by XPath, then this cell's observation as the first walk of that
    /// load. The paid run (experiments/batch PilotExecutor) and the observation dump (RealPilotMode) build
    /// observations only through here. <paramref name="checkLoad"/> runs after the markers are set and
    /// before the walk, and may throw. <paramref name="beforeWalk"/> (the pilot's scoring loads only:
    /// the mutation window of addendum (а′)) runs after it, immediately before the walk; it must not change
    /// the DOM. On an exception the context is closed; otherwise the caller closes it.
    /// </summary>
    public static async Task<(IBrowserContext Ctx, IPage Page, LoadStats Stats, int MarkersSet, string ObsText,
                              IReadOnlyList<ElementData> Raw)> ObserveCellAsync(
        IBrowser browser, string url, byte[] body, DateTime? fixedTime, string? shimJs,
        IEnumerable<(string Id, string Xpath)> markers, string bundle, string encoding,
        IReadOnlySet<string> volIds, IReadOnlySet<string> volClasses, Action<LoadStats, int>? checkLoad = null,
        Func<IPage, Task>? beforeWalk = null)
    {
        var (ctx, page, stats) = await LoadAsync(browser, url, body, fixedTime, shimJs);
        try
        {
            var set = await SetMarkersAsync(page, markers);
            checkLoad?.Invoke(stats, set);
            if (beforeWalk is not null)
            {
                await beforeWalk(page);
            }
            var (obsText, rawWithAnchors, _) = await Observation.BuildObservationAsync(
                page, bundle, encoding, volIds, volClasses);
            return (ctx, page, stats, set, obsText, rawWithAnchors);
        }
        catch
        {
            await ctx.CloseAsync();
            throw;
        }
    }

    /// <summary>
    /// Addendum (а‴), scoring and survival loads only: pauses the page clock at its current time — the fixed time the
    /// loader set before navigation (Clock.SetFixedTime, which installs Playwright's clock), i.e. Date.now() — with no
    /// forward jump. Afterwards no timer, interval or animation frame runs; none is fired by the pause.
    /// </summary>
    public static Task PauseClockAsync(IPage page, DateTime fixedTime) => page.Context.Clock.PauseAtAsync(fixedTime);

    /// <summary>One load of the page, not evaluated (addendum (а″): after every browser start, a warm-up load).</summary>
    public static async Task WarmUpAsync(IBrowser browser, string url, byte[] body, DateTime? fixedTime, string? shimJs)
    {
        var (ctx, _, _) = await LoadAsync(browser, url, body, fixedTime, shimJs);
        await ctx.CloseAsync();
    }

    /// <summary>
    /// Role of an rp_candidates.js candidate: the role table of pilot_rule.md §5, the same function as
    /// rp_common.role_of (Python). Null where rp_common.role_of raises (no role).
    /// </summary>
    public static string? RoleOf(JsonElement c)
    {
        static string? Str(JsonElement c, string n) =>
            c.TryGetProperty(n, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : null;
        var tok = (Str(c, "roleAttr") ?? "").Trim().Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries);
        if (tok.Length > 0)
        {
            return tok[0].ToLowerInvariant();
        }
        switch (Str(c, "tag"))
        {
            case "a": return "link";
            case "button": return "button";
            case "select":
                var multiple = c.TryGetProperty("multiple", out var m) && m.ValueKind == JsonValueKind.True;
                var size = c.TryGetProperty("size", out var z) && z.ValueKind == JsonValueKind.Number ? z.GetInt32() : 0;
                return multiple || size > 1 ? "listbox" : "combobox";
            case "textarea": return "textbox";
            case "input":
                return (Str(c, "type") ?? "") switch
                {
                    "button" or "submit" or "reset" or "image" or "file" or "color" => "button",
                    "checkbox" => "checkbox", "radio" => "radio", "range" => "slider", "number" => "spinbutton",
                    "search" => "searchbox",
                    _ => "textbox",
                };
            default: return null;
        }
    }

    public sealed record SurvivalWindow(int Excluded, int Others, int Matches);

    /// <summary>Addendum (е′): the cell whose observation is the September reference and the survival pre-hash.</summary>
    public const string ReferenceBundle = "B_full", ReferenceEncoding = "F1";

    /// <summary>
    /// Addenda (е)/(е′): sha256 of the B_full × F1 observation of the loaded page — the registered observation walk
    /// (Observation.BuildObservationAsync + EncodeF1Json, the walk behind observations_manifest.tsv for that cell;
    /// data-oracle-* stripped, B_full ignores the volatile lists). The same function makes the reference and the
    /// survival pre-hash.
    /// </summary>
    public static async Task<string> SeptemberPreHashAsync(IPage page)
    {
        var none = new HashSet<string>(StringComparer.Ordinal);
        var (obsText, _, _) = await Observation.BuildObservationAsync(page, ReferenceBundle, ReferenceEncoding, none, none);
        return Convert.ToHexString(SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(obsText))).ToLowerInvariant();
    }

    /// <summary>
    /// One reference load (addendum (е′) point 2): the survival load of (д) (no markers, shims, the September clock),
    /// the page clock paused immediately after it (а‴), a mutation window opened, the first walk hashed
    /// (<see cref="SeptemberPreHashAsync"/>), the window closed. Mutations: records in that window (−1: never opened).
    /// The caller starts the browser and makes the warm-up load. <paramref name="pauseClock"/> = false and
    /// <paramref name="beforeWindow"/> are for tests only.
    /// </summary>
    public static async Task<(string Sha256, int Mutations)> SeptemberReferenceLoadAsync(
        IBrowser browser, string url, byte[] body, DateTime fixedTime, string shimJs, bool pauseClock = true,
        Func<IPage, Task>? beforeWindow = null)
    {
        var (ctx, page, stats) = await LoadAsync(browser, url, body, fixedTime, shimJs);
        try
        {
            if (stats.Fulfilled != 1)
            {
                throw new InvalidOperationException($"offline load fulfilled {stats.Fulfilled}/1");
            }
            if (pauseClock)
            {
                await PauseClockAsync(page, fixedTime);
            }
            if (beforeWindow is not null)
            {
                await beforeWindow(page);
            }
            await MutationWindow.OpenAsync(page);
            var sha = await SeptemberPreHashAsync(page);
            return (sha, await MutationWindow.CloseAsync(page));
        }
        finally
        {
            await ctx.CloseAsync();
        }
    }

    /// <summary>
    /// Survival of one locator (addenda (д), (е), (е′)). Up to <paramref name="maxAttempts"/> fresh loads of the September
    /// page (no XPath markers). Per attempt: page clock paused (а‴) → mutation window opened → first walk, its sha256
    /// (<see cref="SeptemberPreHashAsync"/>) must equal the site's pinned reference <paramref name="referenceSha"/>, else
    /// the attempt fails → target by role + name (rp_candidates.js, exactly one candidate) → data-oracle-id set on it →
    /// the frozen Oracle evaluation → window closed: exactly one excluded record (the marker on that element) and 0
    /// others, else the attempt fails. Status "determined" or "undetermined" (unstable DOM; UniqueMatch / MatchesTarget
    /// null). PreHashes: the pre-hash of every attempt; a window with Matches = −1 is an attempt refused by the pre-hash.
    /// <paramref name="insideWindow"/>, <paramref name="pauseClock"/> = false and <paramref name="beforeWindow"/> are
    /// for tests only.
    /// </summary>
    public static async Task<(bool? UniqueMatch, bool? MatchesTarget, int Attempts, string Status, string? FoundXpath,
                              IReadOnlyList<SurvivalWindow> Windows, IReadOnlyList<string> PreHashes)> EvaluateSurvivalAsync(
        IBrowser browser, string url, byte[] body, DateTime fixedTime, string shimJs, string candidatesJs,
        string marker, string role, string name, string locatorRaw, string referenceSha, int maxAttempts = 5,
        Func<IPage, Task>? insideWindow = null, bool pauseClock = true, Func<IPage, Task>? beforeWindow = null)
    {
        if (string.IsNullOrEmpty(referenceSha))
        {
            throw new ArgumentException("survival needs the site's pinned September reference (addendum (е))");
        }
        var none = new HashSet<string>(StringComparer.Ordinal);
        var windows = new List<SurvivalWindow>();
        var preHashes = new List<string>();
        for (int n = 1; n <= maxAttempts; n++)
        {
            var (ctx, page, stats) = await LoadAsync(browser, url, body, fixedTime, shimJs);
            try
            {
                if (stats.Fulfilled != 1)
                {
                    throw new InvalidOperationException($"offline load fulfilled {stats.Fulfilled}/1");
                }
                if (pauseClock)
                {
                    await PauseClockAsync(page, fixedTime);
                }
                if (beforeWindow is not null)
                {
                    await beforeWindow(page);
                }
                await MutationWindow.OpenAsync(page);
                var pre = await SeptemberPreHashAsync(page);
                preHashes.Add(pre);
                if (pre != referenceSha)
                {
                    // (е) point 2.3: pre-hash != pinned → the attempt fails; nothing is evaluated on this load.
                    var wr = await page.EvaluateAsync<int[]>(MutationWindow.CloseExcludingTargetMarkerJs);
                    windows.Add(new SurvivalWindow(wr[0], wr[1], -1));
                    continue;
                }
                var cand = await page.EvaluateAsync<JsonElement>(candidatesJs);
                var hits = cand.GetProperty("candidates").EnumerateArray()
                    .Where(c => RoleOf(c) == role && c.GetProperty("name").GetString() == name).ToList();
                bool? um = null, mt = null;
                string? xpath = null;
                if (hits.Count == 1)
                {
                    xpath = hits[0].GetProperty("xpath").GetString()!;
                    if (await page.EvaluateAsync<bool>(MutationWindow.MarkTargetJs, new object[] { xpath, marker }))
                    {
                        // Same as RealPilotMode.SurvivalAsync: the frozen Oracle, resolution only.
                        var (type, value) = GroundingRunner.ParseLocatorForReplay(locatorRaw);
                        var oracleRef = new OracleRef(marker);
                        var target = await Oracle.FindOracleElementAsync(page, oracleRef);
                        var ev = await Oracle.EvaluateLocatorAsync(page, type, value, target, Array.Empty<ElementData>(),
                            oracleRef.OracleId, _ => true, null, none, none, Array.Empty<string>());
                        (um, mt) = (ev.PredicateUniqueMatch, ev.PredicateMatchesOracle);
                    }
                }
                if (insideWindow is not null)
                {
                    await insideWindow(page);
                }
                var w = await page.EvaluateAsync<int[]>(MutationWindow.CloseExcludingTargetMarkerJs);
                windows.Add(new SurvivalWindow(w[0], w[1], hits.Count));
                if (um is not null && w[0] == 1 && w[1] == 0)
                {
                    return (um, mt, n, "determined", xpath, windows, preHashes);
                }
            }
            finally
            {
                await ctx.CloseAsync();
            }
        }
        return (null, null, maxAttempts, "undetermined", null, windows, preHashes);
    }
}

/// <summary>
/// The mutation window of addenda (а′) / (д). <see cref="OpenAsync"/>: a MutationObserver (subtree, attributes,
/// childList, characterData) on document and on every open shadow root present then, keeping every record, and a
/// counter of shadow roots attached later. The close calls read, in one synchronous page call, the records already
/// delivered + observer.takeRecords() + attached shadow roots. Opening and closing do not change the DOM. A
/// MutationObserver does not see non-attribute property changes (value, checkedness, :hover/:focus): a declared limit.
/// </summary>
internal static class MutationWindow
{
    public const string OpenJs = @"() => {
        const opts = { subtree: true, attributes: true, childList: true, characterData: true };
        const st = { records: [], shadowAttached: 0 };
        const mo = new MutationObserver(rs => { for (const r of rs) st.records.push(r); });
        const roots = [document];
        const visit = root => {
            for (const el of root.querySelectorAll('*')) {
                if (el.shadowRoot) { roots.push(el.shadowRoot); visit(el.shadowRoot); }
            }
        };
        visit(document);
        for (const r of roots) mo.observe(r, opts);
        const attach = Element.prototype.attachShadow;
        Element.prototype.attachShadow = function (...a) { st.shadowAttached++; return attach.apply(this, a); };
        window.__barMutationWindow = { mo, st };
        return roots.length;
    }";

    /// <summary>Every record counts (pilot scoring: the markers are set before the window opens). −1: never opened.</summary>
    public const string CloseJs = @"() => {
        const w = window.__barMutationWindow;
        if (!w) return -1;
        for (const r of w.mo.takeRecords()) w.st.records.push(r);
        return w.st.records.length + w.st.shadowAttached;
    }";

    /// <summary>Survival (д): sets data-oracle-id on the element of this load's XPath (the role + name match).</summary>
    public const string MarkTargetJs = @"([xpath, id]) => {
        const el = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
        if (!el) return false;
        window.__barSurvivalTarget = el;
        el.setAttribute('data-oracle-id', id);
        return true;
    }";

    /// <summary>
    /// Survival (д): [excluded, others] — excluded = records with type 'attributes', attributeName 'data-oracle-id' and
    /// target === the marked element; others = every other record + attached shadow roots. [−1, −1]: never opened.
    /// </summary>
    public const string CloseExcludingTargetMarkerJs = @"() => {
        const w = window.__barMutationWindow;
        if (!w) return [-1, -1];
        for (const r of w.mo.takeRecords()) w.st.records.push(r);
        const el = window.__barSurvivalTarget;
        const excluded = w.st.records.filter(r => el !== undefined && r.type === 'attributes'
            && r.attributeName === 'data-oracle-id' && r.target === el).length;
        return [excluded, w.st.records.length - excluded + w.st.shadowAttached];
    }";

    public static Task OpenAsync(IPage page) => page.EvaluateAsync<int>(OpenJs);

    /// <summary>Mutations in the window (−1: the window was never opened — never counts as unchanged).</summary>
    public static Task<int> CloseAsync(IPage page) => page.EvaluateAsync<int>(CloseJs);
}
