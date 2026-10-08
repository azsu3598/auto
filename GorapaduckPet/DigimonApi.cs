using System.IO;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json.Serialization;
using System.Windows.Media;
using System.Windows.Media.Imaging;

namespace GorapaduckPet;

public sealed class DigimonProfile
{
    [JsonPropertyName("id")] public int Id { get; set; }
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("images")] public List<DigimonImage> Images { get; set; } = [];
    [JsonPropertyName("levels")] public List<DigimonLevel> Levels { get; set; } = [];
    [JsonPropertyName("attributes")] public List<DigimonAttribute> Attributes { get; set; } = [];
    [JsonPropertyName("nextEvolutions")] public List<DigimonEvolution> NextEvolutions { get; set; } = [];
}

public sealed class DigimonImage { [JsonPropertyName("href")] public string Href { get; set; } = ""; }
public sealed class DigimonLevel { [JsonPropertyName("level")] public string Level { get; set; } = ""; }
public sealed class DigimonAttribute { [JsonPropertyName("attribute")] public string Attribute { get; set; } = ""; }
public sealed class DigimonEvolution
{
    [JsonPropertyName("id")] public int Id { get; set; }
    [JsonPropertyName("digimon")] public string Digimon { get; set; } = "";
    [JsonPropertyName("condition")] public string Condition { get; set; } = "";
    [JsonPropertyName("image")] public string Image { get; set; } = "";
}

public sealed class DigimonApiService
{
    private readonly HttpClient _http = new() { BaseAddress = new Uri("https://digi-api.com/api/v1/"), Timeout = TimeSpan.FromSeconds(15) };

    public async Task<DigimonProfile> GetDigimonAsync(string name)
    {
        var result = await _http.GetFromJsonAsync<DigimonProfile>($"digimon/{Uri.EscapeDataString(name)}");
        return result ?? throw new InvalidOperationException("디지몬 데이터를 읽지 못했습니다.");
    }

    public async Task<BitmapSource> GetTransparentImageAsync(string url)
    {
        var bytes = await _http.GetByteArrayAsync(url);
        using var memory = new MemoryStream(bytes);
        var decoder = BitmapDecoder.Create(memory, BitmapCreateOptions.PreservePixelFormat, BitmapCacheOption.OnLoad);
        var source = new FormatConvertedBitmap(decoder.Frames[0], PixelFormats.Bgra32, null, 0);
        var width = source.PixelWidth;
        var height = source.PixelHeight;
        var stride = width * 4;
        var pixels = new byte[stride * height];
        source.CopyPixels(pixels, stride, 0);
        RemoveConnectedWhiteBackground(pixels, width, height, stride);
        var bitmap = BitmapSource.Create(width, height, source.DpiX, source.DpiY, PixelFormats.Bgra32, null, pixels, stride);
        bitmap.Freeze();
        return bitmap;
    }

    private static void RemoveConnectedWhiteBackground(byte[] pixels, int width, int height, int stride)
    {
        var visited = new bool[width * height];
        var queue = new Queue<int>();

        void Add(int x, int y)
        {
            if (x < 0 || y < 0 || x >= width || y >= height) return;
            var cell = y * width + x;
            if (visited[cell]) return;
            visited[cell] = true;
            var p = y * stride + x * 4;
            if (pixels[p] < 232 || pixels[p + 1] < 232 || pixels[p + 2] < 232) return;
            pixels[p + 3] = 0;
            queue.Enqueue(cell);
        }

        for (var x = 0; x < width; x++) { Add(x, 0); Add(x, height - 1); }
        for (var y = 0; y < height; y++) { Add(0, y); Add(width - 1, y); }
        while (queue.Count > 0)
        {
            var cell = queue.Dequeue();
            var x = cell % width;
            var y = cell / width;
            Add(x - 1, y); Add(x + 1, y); Add(x, y - 1); Add(x, y + 1);
        }
    }
}

public static class EvolutionEngine
{
    private static readonly string[] Bright = ["Agumon", "Greymon", "Angemon", "Holy", "Garurumon", "Tailmon", "Leomon", "War Greymon", "Metal Greymon"];
    private static readonly string[] Dark = ["Black", "Devimon", "Numemon", "Sukamon", "Raremon", "Skull", "Virus", "Bakemon", "Death", "Mugendramon"];

    public static (DigimonEvolution? Choice, string Reason) Choose(DigimonProfile current, PetSettings state)
    {
        var candidates = current.NextEvolutions
            .Where(x => !x.Condition.Contains("Warp", StringComparison.OrdinalIgnoreCase))
            .Where(x => !x.Condition.Contains("with ", StringComparison.OrdinalIgnoreCase))
            .GroupBy(x => x.Id).Select(x => x.First()).ToList();
        if (candidates.Count == 0) candidates = current.NextEvolutions.GroupBy(x => x.Id).Select(x => x.First()).ToList();
        if (candidates.Count == 0) return (null, "API에 다음 진화 정보가 없습니다.");

        var isDark = state.Bond < 35 || state.CareMistakes >= 6;
        var isBright = state.Bond >= 70 && state.CareMistakes <= 2 && state.Mood >= 65;
        IEnumerable<DigimonEvolution> preferred = isDark
            ? candidates.Where(x => Dark.Any(k => x.Digimon.Contains(k, StringComparison.OrdinalIgnoreCase)))
            : isBright
                ? candidates.Where(x => Bright.Any(k => x.Digimon.Contains(k, StringComparison.OrdinalIgnoreCase)))
                : candidates.Where(x => !Dark.Any(k => x.Digimon.Contains(k, StringComparison.OrdinalIgnoreCase)) && !Bright.Any(k => x.Digimon.Contains(k, StringComparison.OrdinalIgnoreCase)));

        var pool = preferred.ToList();
        if (pool.Count == 0) pool = candidates;
        var index = (HashCode.Combine(current.Id, state.CareMistakes, (int)state.Bond) & int.MaxValue) % pool.Count;
        var reason = isDark
            ? $"유대감 {state.Bond:0}, 돌봄 실수 {state.CareMistakes}회로 어두운 분기가 선택됐어요."
            : isBright
                ? $"유대감 {state.Bond:0}과 좋은 관리 상태로 정석 분기가 선택됐어요."
                : $"현재 유대감 {state.Bond:0}과 관리 기록에 따라 중립 분기가 선택됐어요.";
        return (pool[index], reason);
    }
}
