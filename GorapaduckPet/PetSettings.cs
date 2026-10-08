using System.IO;
using System.Text.Json;

namespace GorapaduckPet;

public sealed class PetSettings
{
    public string PetId { get; set; } = Guid.NewGuid().ToString("N");
    public double Scale { get; set; } = 0.72;
    public double Speed { get; set; } = 2.2;
    public bool Wander { get; set; } = true;
    public bool AlwaysOnTop { get; set; } = true;
    public bool HideForFullscreen { get; set; } = true;
    public double LastLeft { get; set; } = double.NaN;
    public double LastTop { get; set; } = double.NaN;
    public double Fullness { get; set; } = 82;
    public double Energy { get; set; } = 86;
    public double Mood { get; set; } = 92;
    public double Bond { get; set; } = 55;
    public double Growth { get; set; }
    public int CareMistakes { get; set; }
    public int EvolutionCount { get; set; }
    public string DigimonName { get; set; } = "DigiEgg";
    public int DigimonId { get; set; }
    public string DigimonLevel { get; set; } = "Egg";
    public List<string> EvolutionHistory { get; set; } = ["DigiEgg"];

    public PetSettings Copy() => (PetSettings)MemberwiseClone();
}

public static class SettingsStore
{
    private static readonly string Folder = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "DigiDesktopPet");
    private static readonly string FilePath = Path.Combine(Folder, "settings.json");

    private static readonly object Gate = new();
    private static List<PetSettings> _pets = [];

    public static IReadOnlyList<PetSettings> LoadAll()
    {
        lock (Gate)
        {
            try
            {
                if (!File.Exists(FilePath))
                {
                    _pets = [new PetSettings()];
                    SaveAllCore();
                    return _pets;
                }

                var json = File.ReadAllText(FilePath);
                using var document = JsonDocument.Parse(json);
                if (document.RootElement.TryGetProperty("Pets", out _))
                {
                    _pets = JsonSerializer.Deserialize<PetRosterData>(json)?.Pets ?? [];
                }
                else
                {
                    var legacyPet = JsonSerializer.Deserialize<PetSettings>(json) ?? new PetSettings();
                    _pets = [legacyPet];
                }

                if (_pets.Count == 0) _pets.Add(new PetSettings());
                if (_pets.Count > 6) _pets = _pets.Take(6).ToList();
                foreach (var pet in _pets)
                {
                    if (string.IsNullOrWhiteSpace(pet.PetId)) pet.PetId = Guid.NewGuid().ToString("N");
                    pet.EvolutionHistory ??= [pet.DigimonName];
                }
                SaveAllCore();
                return _pets;
            }
            catch
            {
                _pets = [new PetSettings()];
                return _pets;
            }
        }
    }

    public static void Save(PetSettings settings)
    {
        lock (Gate)
        {
            var index = _pets.FindIndex(x => x.PetId == settings.PetId);
            if (index >= 0) _pets[index] = settings;
            else if (_pets.Count < 6) _pets.Add(settings);
            SaveAllCore();
        }
    }

    public static bool Add(PetSettings settings)
    {
        lock (Gate)
        {
            if (_pets.Count >= 6) return false;
            _pets.Add(settings);
            SaveAllCore();
            return true;
        }
    }

    public static void Remove(string petId)
    {
        lock (Gate)
        {
            _pets.RemoveAll(x => x.PetId == petId);
            SaveAllCore();
        }
    }

    public static void SaveAll()
    {
        lock (Gate) SaveAllCore();
    }

    private static void SaveAllCore()
    {
        try
        {
            Directory.CreateDirectory(Folder);
            var data = new PetRosterData { Pets = _pets };
            File.WriteAllText(FilePath, JsonSerializer.Serialize(data, new JsonSerializerOptions { WriteIndented = true }));
        }
        catch { /* 저장 실패가 앱 종료를 막지 않도록 한다. */ }
    }
}

public sealed class PetRosterData
{
    public int Version { get; set; } = 2;
    public List<PetSettings> Pets { get; set; } = [];
}
