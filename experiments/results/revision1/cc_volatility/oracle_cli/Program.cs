// OracleValueCli — classifies single class / id values with the Oracle's own value predicates.
//
// Input  (stdin, JSONL):  {"t":"class"|"id","v":"<value>"}
// Output (stdout, JSONL): {"t":...,"v":...,"flag":true|false}
//
// The predicates Oracle.IsVolatileClass / Oracle.IsVolatileId are private static; they are
// invoked by reflection so that the classification is the unchanged Oracle code. No truth lists
// are passed (external sites have none), so list-based checks do not apply.

using System.Reflection;
using System.Text;
using System.Text.Json;
using BoundedAgents.Shared.Oracle;

const BindingFlags Flags = BindingFlags.NonPublic | BindingFlags.Static;
var isClass = typeof(Oracle).GetMethod("IsVolatileClass", Flags, [typeof(string)])
              ?? throw new InvalidOperationException("Oracle.IsVolatileClass(string) not found");
var isId = typeof(Oracle).GetMethod("IsVolatileId", Flags, [typeof(string)])
           ?? throw new InvalidOperationException("Oracle.IsVolatileId(string) not found");
if (isClass.ReturnType != typeof(bool) || isId.ReturnType != typeof(bool))
    throw new InvalidOperationException("unexpected predicate signature");

if (args.Contains("--describe"))
{
    Console.WriteLine($"assembly={typeof(Oracle).Assembly.Location}");
    Console.WriteLine($"class={isClass}");
    Console.WriteLine($"id={isId}");
    return 0;
}

Console.InputEncoding = Encoding.UTF8;
var stdout = new StreamWriter(Console.OpenStandardOutput(), new UTF8Encoding(false)) { AutoFlush = false };
string? line;
long n = 0;
while ((line = Console.In.ReadLine()) is not null)
{
    if (line.Length == 0) continue;
    using var doc = JsonDocument.Parse(line);
    var t = doc.RootElement.GetProperty("t").GetString();
    var v = doc.RootElement.GetProperty("v").GetString() ?? "";
    var method = t switch
    {
        "class" => isClass,
        "id" => isId,
        _ => throw new InvalidOperationException($"unknown type '{t}' on line {n + 1}")
    };
    var flag = (bool)method.Invoke(null, [v])!;
    stdout.WriteLine(JsonSerializer.Serialize(new { t, v, flag }));
    n++;
}
stdout.Flush();
Console.Error.WriteLine($"[oracle_cli] classified {n} values");
return 0;
