using System.Text;
using System.Text.Json;
using BoundedAgents.Shared.Oracle;

namespace BoundedAgents.Shared.Harness;

/// <summary>
/// Observation encoders (Axis B): serialize a bundle-projected element list into each wire
/// format (F0 HTML, F1/F2 JSON, F3 linearized, flat-kv) plus the F2 round-trip check.
/// </summary>
public static class ObservationEncoders
{
    // -----------------------------------------------------------------------
    // F2 key abbreviation map (bijective — enables round-trip verification)
    // -----------------------------------------------------------------------

    internal static readonly IReadOnlyDictionary<string, string> F2KeyMap =
        new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["tag"] = "t",
            ["text"] = "tx",
            ["id"] = "i",
            ["data-testid"] = "dt",
            ["name"] = "nm",
            ["type"] = "ty",
            ["for"] = "fr",
            ["role"] = "ro",
            ["aria-label"] = "al",
            ["placeholder"] = "ph",
            ["alt"] = "at",
            ["title"] = "tl",
            ["href"] = "hr",
            ["value"] = "vl",
            ["class"] = "cl",
            ["src"] = "sc",
            ["disabled"] = "ds",
            ["checked"] = "ck",
            ["selected"] = "sd",
            ["aria-expanded"] = "aex",
            ["aria-selected"] = "asl",
            ["aria-checked"] = "ack",
            ["aria-disabled"] = "ads",
            ["aria-required"] = "arq",
            ["aria-controls"] = "aco",
            ["aria-haspopup"] = "ahp",
            ["aria-level"] = "alv",
            ["tabindex"] = "ti",
            ["aria-hidden"] = "ahd",
            ["aria-live"] = "ali",
            ["aria-labelledby"] = "alb",
            ["aria-describedby"] = "adb",
            ["is_shadow"] = "sh",
        };

    internal static readonly IReadOnlyDictionary<string, string> F2KeyMapReverse =
        new Dictionary<string, string>(
            F2KeyMap.ToDictionary(kv => kv.Value, kv => kv.Key),
            StringComparer.OrdinalIgnoreCase);

    // -----------------------------------------------------------------------
    // Encoding — Axis B
    // -----------------------------------------------------------------------

    private static readonly HashSet<string> _voidElements = new(StringComparer.OrdinalIgnoreCase)
        { "input", "br", "hr", "img", "link", "meta", "area", "base", "col",
          "embed", "param", "source", "track", "wbr" };

    /// <summary>
    /// True when an element carries any attribute or non-blank text — i.e. it contributes
    /// something to the observation. Empty elements are skipped by every encoder and by the
    /// D→O pipeline filter.
    /// </summary>
    internal static bool HasContent(ElementData el) =>
        el.Attrs.Count > 0 || !string.IsNullOrWhiteSpace(el.Text);

    /// <summary>
    /// F0: Raw HTML reconstruction from filtered element list (verbose baseline).
    /// Each element serialised as an HTML tag with its filtered attributes and text.
    /// </summary>
    public static string EncodeF0Html(IReadOnlyList<ElementData> elements)
    {
        var sb = new StringBuilder();
        foreach (var el in elements)
        {
            if (!HasContent(el))
            {
                continue;
            }

            sb.Append('<').Append(el.Tag);
            if (el.IsInShadowRoot)
            {
                sb.Append(" data-shadow=\"true\"");
            }

            foreach (var (k, v) in el.Attrs)
            {
                if (string.IsNullOrEmpty(v))
                {
                    continue;
                }

                sb.Append(' ').Append(k).Append("=\"")
                  .Append(v.Replace("&", "&amp;").Replace("\"", "&quot;"))
                  .Append('"');
            }
            var txt = el.Text.Replace("\n", " ").Trim();
            if (_voidElements.Contains(el.Tag))
            {
                sb.AppendLine(" />");
            }
            else if (!string.IsNullOrWhiteSpace(txt))
            {
                sb.Append('>').Append(txt.Replace("&", "&amp;").Replace("<", "&lt;"))
                  .Append("</").Append(el.Tag).AppendLine(">");
            }
            else
            {
                sb.Append("></").Append(el.Tag).AppendLine(">");
            }
        }
        return sb.ToString().TrimEnd();
    }

    /// <summary>
    /// F1: Flat structured JSON, full keys (experiments/docs/SCHEMA.md §3).
    /// Compact (no whitespace) — token cost measured on this form.
    /// </summary>
    public static string EncodeF1Json(IReadOnlyList<ElementData> elements)
    {
        var arr = new List<Dictionary<string, string>>();
        foreach (var el in elements)
        {
            if (!HasContent(el))
            {
                continue;
            }

            var obj = new Dictionary<string, string> { ["tag"] = el.Tag };
            var txt = el.Text.Replace("\n", " ").Trim();
            if (!string.IsNullOrWhiteSpace(txt))
            {
                obj["text"] = txt;
            }

            foreach (var (k, v) in el.Attrs)
            {
                if (!string.IsNullOrEmpty(v))
                {
                    obj[k] = v;
                }
            }

            if (el.IsInShadowRoot)
            {
                obj["is_shadow"] = "true";
            }

            // obj always carries the "tag" key; Count > 1 means it also has at least one
            // real attribute or text field — skip elements that are tag-only.
            if (obj.Count > 1)
            {
                arr.Add(obj);
            }
        }
        return JsonSerializer.Serialize(arr, new JsonSerializerOptions { WriteIndented = false });
    }

    /// <summary>
    /// F2: Compact JSON with abbreviated keys (lossless minification of F1).
    /// Key map is bijective — round-trip verifiable via VerifyF2RoundTrip.
    /// </summary>
    public static string EncodeF2CompactJson(IReadOnlyList<ElementData> elements)
    {
        var arr = new List<Dictionary<string, string>>();
        foreach (var el in elements)
        {
            if (!HasContent(el))
            {
                continue;
            }

            var obj = new Dictionary<string, string>
            {
                [F2KeyMap["tag"]] = el.Tag
            };
            var txt = el.Text.Replace("\n", " ").Trim();
            if (!string.IsNullOrWhiteSpace(txt))
            {
                obj[F2KeyMap["text"]] = txt;
            }

            foreach (var (k, v) in el.Attrs)
            {
                if (string.IsNullOrEmpty(v))
                {
                    continue;
                }

                var shortKey = F2KeyMap.TryGetValue(k, out var sk) ? sk : k;
                obj[shortKey] = v;
            }
            if (el.IsInShadowRoot)
            {
                obj[F2KeyMap["is_shadow"]] = "true";
            }

            // obj always carries the "tag" key; Count > 1 means it also has at least one
            // real attribute or text field — skip elements that are tag-only.
            if (obj.Count > 1)
            {
                arr.Add(obj);
            }
        }
        return JsonSerializer.Serialize(arr, new JsonSerializerOptions { WriteIndented = false });
    }

    /// <summary>
    /// Expand F2 abbreviated keys back to full key names for round-trip verification.
    /// </summary>
    public static string ExpandF2Keys(string f2Json)
    {
        var objs = JsonSerializer.Deserialize<List<Dictionary<string, JsonElement>>>(f2Json)
            ?? new List<Dictionary<string, JsonElement>>();
        var expanded = objs.Select(obj =>
        {
            var full = new Dictionary<string, string>();
            foreach (var (k, v) in obj)
            {
                var fullKey = F2KeyMapReverse.TryGetValue(k, out var fk) ? fk : k;
                full[fullKey] = v.GetString() ?? "";
            }
            return full;
        }).ToList();
        return JsonSerializer.Serialize(expanded, new JsonSerializerOptions { WriteIndented = false });
    }

    /// <summary>
    /// Round-trip check: expand F2 abbreviated keys and compare field-by-field with F1.
    /// Returns true if every element and every field matches exactly.
    /// </summary>
    public static bool VerifyF2RoundTrip(string f1Text, string f2Text)
    {
        try
        {
            var opts = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
            var f1 = JsonSerializer.Deserialize<List<Dictionary<string, string>>>(f1Text, opts)
                     ?? new();
            var f2raw = JsonSerializer.Deserialize<List<Dictionary<string, string>>>(f2Text, opts)
                        ?? new();

            if (f1.Count != f2raw.Count)
            {
                return false;
            }

            for (int i = 0; i < f1.Count; i++)
            {
                var f1el = f1[i];
                // Expand f2 keys
                var f2el = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
                foreach (var (k, v) in f2raw[i])
                {
                    var fullKey = F2KeyMapReverse.TryGetValue(k, out var fk) ? fk : k;
                    f2el[fullKey] = v;
                }
                if (f1el.Count != f2el.Count)
                {
                    return false;
                }

                foreach (var (k, v) in f1el)
                {
                    if (!f2el.TryGetValue(k, out var f2v) || f2v != v)
                    {
                        return false;
                    }
                }
            }
            return true;
        }
        catch
        {
            return false;
        }
    }

    /// <summary>
    /// F3: Compact linearized DSL — one element per line.
    /// Format: tag [key=val ...] [{text}]
    /// Values are quoted when they contain spaces, =, ", {, or }.
    /// </summary>
    public static string EncodeF3Linearized(IReadOnlyList<ElementData> elements)
    {
        var sb = new StringBuilder();
        foreach (var el in elements)
        {
            if (!HasContent(el))
            {
                continue;
            }

            if (el.IsInShadowRoot)
            {
                sb.Append("[S] ");
            }

            sb.Append(el.Tag);
            foreach (var (k, v) in el.Attrs)
            {
                if (string.IsNullOrEmpty(v))
                {
                    continue;
                }

                sb.Append(' ').Append(k).Append('=');
                if (NeedsQuoting(v))
                {
                    sb.Append('"').Append(v.Replace("\\", "\\\\").Replace("\"", "\\\"")).Append('"');
                }
                else
                {
                    sb.Append(v);
                }
            }
            var txt = el.Text.Replace("\n", " ").Trim();
            if (!string.IsNullOrWhiteSpace(txt))
            {
                var escapedTxt = txt.Replace("\\", "\\\\").Replace("{", "\\{").Replace("}", "\\}");
                sb.Append(" {").Append(escapedTxt).Append('}');
            }
            sb.AppendLine();
        }
        return sb.ToString().TrimEnd();
    }

    private static bool NeedsQuoting(string s) =>
        s.Any(c => c is ' ' or '=' or '"' or '{' or '}' or '\t' or '\n' or '\r');

    /// <summary>
    /// Encodes elements as one flat key=value line each. Kept for smoke-test
    /// backward-compatibility only — not one of the F0-F4 encodings under study.
    /// </summary>
    public static string EncodeFlatKv(IReadOnlyList<ElementData> elements)
    {
        var sb = new StringBuilder();
        foreach (var el in elements)
        {
            if (!HasContent(el))
            {
                continue;
            }

            var parts = new List<string> { $"tag={Quote(el.Tag)}" };
            if (!string.IsNullOrWhiteSpace(el.Text))
            {
                parts.Add($"text={Quote(el.Text.Replace("\n", " ").Trim())}");
            }

            foreach (var (k, v) in el.Attrs)
            {
                if (!string.IsNullOrEmpty(v))
                {
                    parts.Add($"{k}={Quote(v)}");
                }
            }

            // parts[0] is always the tag; Count > 1 means it also has text or an
            // attribute — skip elements that are tag-only.
            if (parts.Count > 1)
            {
                sb.AppendLine(string.Join("  ", parts));
            }
        }
        return sb.ToString().TrimEnd();
    }

    private static string Quote(string s) => $"'{s.Replace("'", "\\'")}'";
}
