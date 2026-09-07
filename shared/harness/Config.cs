using DotNetEnv;

namespace BoundedAgents.Shared.Harness;

/// <summary>
/// Loads .env from the repo root and exposes typed accessors.
/// All project env vars use the BAR_ prefix to avoid collision with OS-level AZURE_* vars.
/// API keys are read directly in LlmClient — Config only exposes endpoints.
/// </summary>
public static class Config
{
    static Config()
    {
        var envPath = FindEnvFile();
        if (envPath is not null)
        {
            Env.Load(envPath, new LoadOptions(setEnvVars: true, clobberExistingVars: false));
        }
    }

    private static string? FindEnvFile()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null)
        {
            var candidate = Path.Combine(dir.FullName, ".env");
            if (File.Exists(candidate))
            {
                return candidate;
            }

            dir = dir.Parent;
        }
        return null;
    }

    public static string AzureOpenAiEndpoint => Required("BAR_AZURE_OPENAI_ENDPOINT");
    public static string AzureOpenAiApiVersion => Optional("BAR_AZURE_OPENAI_API_VERSION") ?? "2024-12-01-preview";
    public static string AzureInferenceEndpoint => Required("BAR_AZURE_INFERENCE_ENDPOINT");
    public static string AzureAnthropicEndpoint => Required("BAR_AZURE_ANTHROPIC_ENDPOINT");
    public static string TestbedBaseUrl => Optional("BAR_TESTBED_BASE_URL") ?? "http://localhost:8000";
    public static int RandomSeed => int.Parse(Optional("BAR_RANDOM_SEED") ?? "42");

    public static string Get(string key, bool required = true)
    {
        var val = Environment.GetEnvironmentVariable(key);
        if (required && string.IsNullOrEmpty(val))
        {
            throw new InvalidOperationException(
                $"Required env var '{key}' is not set. Copy .env.example to .env and fill in values.");
        }

        return val ?? string.Empty;
    }

    private static string Required(string key) => Get(key, required: true);
    private static string? Optional(string key) => Environment.GetEnvironmentVariable(key);
}
