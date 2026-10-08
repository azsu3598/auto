using System.Drawing;
using System.Threading;
using System.Windows;
using Forms = System.Windows.Forms;

namespace GorapaduckPet;

public partial class App : System.Windows.Application
{
    private Forms.NotifyIcon? _trayIcon;
    private readonly List<PetWindow> _petWindows = [];
    private Mutex? _singleInstanceMutex;

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        _singleInstanceMutex = new Mutex(true, "DigiDesktopPet.SingleInstance", out var isFirstInstance);
        if (!isFirstInstance)
        {
            System.Windows.MessageBox.Show("디지몬 데스크톱 펫이 이미 실행 중입니다.\n작업표시줄 트레이를 확인해 주세요.", "이미 실행 중");
            Shutdown();
            return;
        }

        foreach (var settings in SettingsStore.LoadAll()) CreatePetWindow(settings);

        var menu = new Forms.ContextMenuStrip();
        menu.Items.Add("새 디지타마 추가", null, (_, _) => Dispatcher.Invoke(AddPet));
        menu.Items.Add("모두 보이기 / 숨기기", null, (_, _) => Dispatcher.Invoke(TogglePets));
        menu.Items.Add(new Forms.ToolStripSeparator());
        menu.Items.Add("종료", null, (_, _) => Dispatcher.Invoke(ExitApp));

        _trayIcon = new Forms.NotifyIcon
        {
            Text = "디지몬 데스크톱 펫",
            Icon = SystemIcons.Application,
            ContextMenuStrip = menu,
            Visible = true
        };
        _trayIcon.DoubleClick += (_, _) => Dispatcher.Invoke(TogglePets);
    }

    private void CreatePetWindow(PetSettings settings)
    {
        var pet = new PetWindow(settings);
        _petWindows.Add(pet);
        pet.Show();
    }

    public void AddPet()
    {
        if (_petWindows.Count >= 6)
        {
            System.Windows.MessageBox.Show("동시에 키울 수 있는 디지몬은 최대 6마리입니다.", "디지타마 추가");
            return;
        }

        var settings = new PetSettings
        {
            LastLeft = SystemParameters.WorkArea.Left + 20 + _petWindows.Count * 62,
            LastTop = SystemParameters.WorkArea.Bottom - 470
        };
        if (!SettingsStore.Add(settings)) return;
        CreatePetWindow(settings);
    }

    public void OpenSettings(PetWindow pet)
    {
        var window = new SettingsWindow(pet.Settings) { Owner = pet };
        if (window.ShowDialog() == true)
        {
            pet.ApplySettings(window.Result);
            SettingsStore.Save(window.Result);
        }
    }

    public void RemovePet(PetWindow pet)
    {
        var name = pet.Settings.DigimonName == "DigiEgg" ? "이 디지타마" : pet.Settings.DigimonName;
        var answer = System.Windows.MessageBox.Show($"{name}을(를) 정말 놓아줄까요?\n이 펫의 성장과 진화 기록은 삭제됩니다.",
            "펫 놓아주기", MessageBoxButton.YesNo, MessageBoxImage.Warning);
        if (answer != MessageBoxResult.Yes) return;
        SettingsStore.Remove(pet.Settings.PetId);
        _petWindows.Remove(pet);
        pet.AllowClose = true;
        pet.Close();
    }

    public void TogglePets()
    {
        var shouldShow = !_petWindows.Any(x => x.IsVisible);
        foreach (var pet in _petWindows)
        {
            if (shouldShow) pet.Show(); else pet.Hide();
        }
    }

    public void ExitApp()
    {
        foreach (var pet in _petWindows.ToList())
        {
            SettingsStore.Save(pet.Settings);
            pet.AllowClose = true;
            pet.Close();
        }
        SettingsStore.SaveAll();
        if (_trayIcon is not null)
        {
            _trayIcon.Visible = false;
            _trayIcon.Dispose();
        }
        _singleInstanceMutex?.ReleaseMutex();
        _singleInstanceMutex?.Dispose();
        Shutdown();
    }
}
