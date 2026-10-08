using System.ComponentModel;
using System.Windows;
using System.Windows.Input;
using System.Windows.Threading;

namespace GorapaduckPet;

public partial class PetWindow : Window
{
    private enum PetAction { Walking, Idle, Feeding, Playing, Sleeping, Petted, Evolving }

    private readonly DispatcherTimer _motionTimer = new() { Interval = TimeSpan.FromMilliseconds(40) };
    private readonly DispatcherTimer _lifeTimer = new() { Interval = TimeSpan.FromSeconds(20) };
    private readonly DispatcherTimer _speechTimer = new() { Interval = TimeSpan.FromSeconds(3) };
    private readonly DispatcherTimer _fullscreenTimer = new() { Interval = TimeSpan.FromSeconds(1) };
    private readonly DigimonApiService _api = new();
    private readonly Random _random = new();
    private DigimonProfile? _profile;
    private PetAction _action = PetAction.Walking;
    private DateTime _actionEnds = DateTime.MaxValue;
    private DateTime _nextDirectionChange;
    private double _velocityX = 1;
    private double _animationPhase;
    private bool _dragging;
    private bool _paused;
    private bool _sleeping;
    private bool _hiddenForFullscreen;
    private bool _crisisRecorded;
    private bool _evolutionInProgress;

    public PetSettings Settings { get; private set; }
    public bool AllowClose { get; set; }

    public PetWindow(PetSettings settings)
    {
        InitializeComponent();
        Settings = settings;
        ApplySettings(settings);

        Loaded += async (_, _) =>
        {
            RestorePosition();
            ChooseDirection();
            UpdateStats();
            await LoadCurrentDigimonAsync();
        };

        PetVisual.MouseEnter += (_, _) => StatsPanel.Opacity = 1;
        PetVisual.MouseLeave += (_, _) => StatsPanel.Opacity = 0;
        PetVisual.MouseLeftButtonDown += PetVisual_MouseLeftButtonDown;
        _motionTimer.Tick += MotionTimer_Tick;
        _lifeTimer.Tick += LifeTimer_Tick;
        _speechTimer.Tick += (_, _) => { SpeechBubble.Visibility = Visibility.Collapsed; _speechTimer.Stop(); };
        _fullscreenTimer.Tick += FullscreenTimer_Tick;
        _motionTimer.Start();
        _lifeTimer.Start();
        _fullscreenTimer.Start();
        ShowSpeech("디지타마가 도착했어요!");
    }

    public void ApplySettings(PetSettings settings)
    {
        Settings = settings;
        Width = 360;
        Height = 470;
        PetScaleTransform.ScaleX = Settings.Scale;
        PetScaleTransform.ScaleY = Settings.Scale;
        UpdateSpeechBubblePosition();
        Topmost = Settings.AlwaysOnTop;
        PauseMenu.Header = _paused ? "▶ 돌아다니기 재개" : "⏸ 돌아다니기 일시정지";
    }

    private void UpdateSpeechBubblePosition()
    {
        const double petLayoutHeight = 280;
        const double gapAbovePet = 8;
        SpeechBubble.Margin = new Thickness(8, 0, 8, petLayoutHeight * Settings.Scale + gapAbovePet);
    }

    private bool IsEgg => Settings.DigimonName == "DigiEgg";
    private double EvolutionGoal => IsEgg ? 30 : 100;

    private async Task LoadCurrentDigimonAsync()
    {
        if (IsEgg)
        {
            _profile = null;
            EggVisual.Visibility = Visibility.Visible;
            PetImage.Visibility = Visibility.Collapsed;
            LoadingPanel.Visibility = Visibility.Collapsed;
            PetNameText.Text = "디지타마";
            UpdateStats();
            return;
        }

        try
        {
            LoadingPanel.Visibility = Visibility.Visible;
            LoadingText.Text = "DIGIMON DATA 연결 중…";
            var nextProfile = await _api.GetDigimonAsync(Settings.DigimonName);
            var imageUrl = nextProfile.Images.FirstOrDefault()?.Href;
            if (string.IsNullOrWhiteSpace(imageUrl)) throw new InvalidOperationException("이미지 URL이 없습니다.");
            var nextImage = await _api.GetTransparentImageAsync(imageUrl);

            _profile = nextProfile;
            PetImage.Source = nextImage;
            Settings.DigimonId = _profile.Id;
            Settings.DigimonName = _profile.Name;
            Settings.DigimonLevel = _profile.Levels.FirstOrDefault()?.Level ?? "Unknown";
            PetNameText.Text = _profile.Name;
            EggVisual.Visibility = Visibility.Collapsed;
            PetImage.Visibility = Visibility.Visible;
            PetImage.Opacity = 1;
            LoadingPanel.Visibility = Visibility.Collapsed;
            SettingsStore.Save(Settings);
            UpdateStats();
        }
        catch
        {
            LoadingPanel.Visibility = Visibility.Visible;
            LoadingText.Text = $"{Settings.DigimonName} 데이터를 불러오지 못했어요.\n우클릭 → 데이터 다시 불러오기";
            ShowSpeech("API 연결을 확인해 주세요.");
        }
    }

    private void RestorePosition()
    {
        if (double.IsNaN(Settings.LastLeft) || double.IsNaN(Settings.LastTop))
        {
            Left = SystemParameters.WorkArea.Right - ActualWidth - 36;
            Top = SystemParameters.WorkArea.Bottom - ActualHeight - 18;
            return;
        }
        Left = Clamp(Settings.LastLeft, SystemParameters.VirtualScreenLeft, SystemParameters.VirtualScreenLeft + SystemParameters.VirtualScreenWidth - ActualWidth);
        Top = Clamp(Settings.LastTop, SystemParameters.VirtualScreenTop, SystemParameters.VirtualScreenTop + SystemParameters.VirtualScreenHeight - ActualHeight);
    }

    private void MotionTimer_Tick(object? sender, EventArgs e)
    {
        _animationPhase += .22;
        if (!_sleeping && _action is not PetAction.Walking and not PetAction.Idle && DateTime.Now >= _actionEnds)
            StartAction(Settings.Wander && !_paused ? PetAction.Walking : PetAction.Idle);
        AnimateCurrentAction();

        if (_dragging || _paused || _sleeping || !Settings.Wander || _action != PetAction.Walking) return;
        if (DateTime.Now >= _nextDirectionChange) ChooseDirection();
        Left += _velocityX * Settings.Speed;

        var min = SystemParameters.VirtualScreenLeft;
        var max = SystemParameters.VirtualScreenLeft + SystemParameters.VirtualScreenWidth - ActualWidth;
        if (Left <= min || Left >= max)
        {
            Left = Clamp(Left, min, max);
            _velocityX *= -1;
        }
        Settings.LastLeft = Left;
        Settings.LastTop = Top;
    }

    private async void LifeTimer_Tick(object? sender, EventArgs e)
    {
        Settings.Fullness = Clamp(Settings.Fullness - .8, 0, 100);
        Settings.Energy = Clamp(Settings.Energy + (_sleeping ? 4 : -.3), 0, 100);
        Settings.Mood = Clamp(Settings.Mood - (Settings.Fullness < 25 ? 1.1 : .2), 0, 100);
        Settings.Growth = Clamp(Settings.Growth + 1, 0, EvolutionGoal);

        var crisis = Settings.Fullness < 15 || Settings.Energy < 10 || Settings.Mood < 15;
        if (crisis && !_crisisRecorded)
        {
            Settings.CareMistakes++;
            Settings.Bond = Clamp(Settings.Bond - 6, 0, 100);
            _crisisRecorded = true;
            ShowSpeech("돌봄이 필요해요…");
        }
        else if (!crisis) _crisisRecorded = false;

        UpdateStats();
        SettingsStore.Save(Settings);
        if (Settings.Growth >= EvolutionGoal) await TryEvolveAsync(false);
    }

    private void FullscreenTimer_Tick(object? sender, EventArgs e)
    {
        if (!Settings.HideForFullscreen) return;
        var fullscreen = NativeMethods.IsForegroundFullscreen();
        if (fullscreen && IsVisible) { _hiddenForFullscreen = true; Hide(); }
        else if (!fullscreen && _hiddenForFullscreen) { _hiddenForFullscreen = false; Show(); }
    }

    private void ChooseDirection()
    {
        _velocityX = _random.NextDouble() < .5 ? -1 : 1;
        _nextDirectionChange = DateTime.Now.AddSeconds(_random.Next(4, 11));
        if (_random.NextDouble() < .22)
            ShowSpeech(new[] { "산책 중!", "디지털 월드는 어디지?", "같이 놀자!", "배고프지 않아!" }[_random.Next(4)]);
    }

    private void AddCare(double growth, double bond)
    {
        Settings.Growth = Clamp(Settings.Growth + growth, 0, EvolutionGoal);
        Settings.Bond = Clamp(Settings.Bond + bond, 0, 100);
        SettingsStore.Save(Settings);
        UpdateStats();
        if (Settings.Growth >= EvolutionGoal) _ = TryEvolveAsync(false);
    }

    private async Task TryEvolveAsync(bool userRequested)
    {
        if (_evolutionInProgress) return;
        if (Settings.Growth < EvolutionGoal)
        {
            if (userRequested) ShowSpeech($"진화까지 성장도 {Settings.Growth:0}/{EvolutionGoal:0}");
            return;
        }

        _evolutionInProgress = true;
        try
        {
            string nextName;
            string reason;
            if (IsEgg)
            {
                nextName = "Botamon";
                reason = "따뜻하게 돌본 디지타마가 부화했어요.";
            }
            else
            {
                _profile ??= await _api.GetDigimonAsync(Settings.DigimonName);
                var result = EvolutionEngine.Choose(_profile, Settings);
                if (result.Choice is null)
                {
                    ShowSpeech(result.Reason);
                    return;
                }
                nextName = result.Choice.Digimon;
                reason = result.Reason;
            }

            var previous = IsEgg ? "디지타마" : Settings.DigimonName;
            StartAction(PetAction.Evolving, 3.5);
            ActionEffect.Text = "✨";
            ActionEffect.Visibility = Visibility.Visible;
            ShowSpeech($"{previous} → {nextName}!");
            await Task.Delay(900);
            Settings.DigimonName = nextName;
            Settings.Growth = 0;
            Settings.EvolutionCount++;
            Settings.CareMistakes = 0;
            Settings.EvolutionHistory.Add(nextName);
            await LoadCurrentDigimonAsync();
            SettingsStore.Save(Settings);
            ShowSpeech(reason);
        }
        catch
        {
            ShowSpeech("진화 데이터를 가져오지 못했어요. 다시 시도해 주세요.");
        }
        finally { _evolutionInProgress = false; }
    }

    private void UpdateStats()
    {
        PetNameText.Text = IsEgg ? "디지타마" : Settings.DigimonName;
        StatsText.Text = $"{Settings.DigimonLevel} · 유대 {Settings.Bond:0} · 성장 {Settings.Growth:0}/{EvolutionGoal:0}\n" +
                         $"포만 {(int)Settings.Fullness} · 체력 {(int)Settings.Energy} · 기분 {(int)Settings.Mood}";
    }

    private void ShowSpeech(string text)
    {
        SpeechText.Text = text;
        SpeechBubble.Visibility = Visibility.Visible;
        _speechTimer.Stop();
        _speechTimer.Start();
    }

    private void StartAction(PetAction action, double seconds = 0)
    {
        _action = action;
        _actionEnds = seconds > 0 ? DateTime.Now.AddSeconds(seconds) : DateTime.MaxValue;
        FoodBowl.Visibility = action == PetAction.Feeding ? Visibility.Visible : Visibility.Collapsed;
        PlayBall.Visibility = action == PetAction.Playing ? Visibility.Visible : Visibility.Collapsed;
        ActionEffect.Visibility = action is PetAction.Petted or PetAction.Sleeping or PetAction.Evolving ? Visibility.Visible : Visibility.Collapsed;
        ActionEffect.Text = action switch { PetAction.Sleeping => "Zzz", PetAction.Evolving => "✨", _ => "💛" };
    }

    private void AnimateCurrentAction()
    {
        var direction = _velocityX >= 0 ? 1d : -1d;
        var wave = Math.Sin(_animationPhase);
        FacingTransform.ScaleX = direction;
        FacingTransform.ScaleY = 1;
        BobTransform.X = 0; BobTransform.Y = 0; WaddleTransform.Angle = 0;

        switch (_action)
        {
            case PetAction.Walking:
                BobTransform.Y = Math.Abs(wave) * -8; WaddleTransform.Angle = wave * 5; break;
            case PetAction.Idle:
                FacingTransform.ScaleY = 1 + wave * .025; break;
            case PetAction.Feeding:
                BobTransform.Y = Math.Abs(wave) * 13; WaddleTransform.Angle = wave * 2; break;
            case PetAction.Playing:
                BobTransform.Y = Math.Abs(wave) * -28; WaddleTransform.Angle = wave * 9;
                BallTransform.X = Math.Sin(_animationPhase * .55) * 72;
                BallTransform.Y = -Math.Abs(Math.Cos(_animationPhase * .55)) * 58; break;
            case PetAction.Sleeping:
                WaddleTransform.Angle = -16; FacingTransform.ScaleY = .82; EffectTransform.Y = -8 + wave * 7; break;
            case PetAction.Petted:
                FacingTransform.ScaleY = 1 - Math.Abs(wave) * .09; BobTransform.Y = Math.Abs(wave) * 7; EffectTransform.Y = wave * -13; break;
            case PetAction.Evolving:
                FacingTransform.ScaleX = direction * (1 + Math.Abs(wave) * .16);
                FacingTransform.ScaleY = 1 + Math.Abs(wave) * .16;
                WaddleTransform.Angle = wave * 10; break;
        }
    }

    private void PetVisual_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        if (e.ClickCount != 2) return;
        Settings.Mood = Clamp(Settings.Mood + 7, 0, 100);
        AddCare(5, 4);
        _sleeping = false;
        StartAction(PetAction.Petted, 1.7);
        ShowSpeech(IsEgg ? "알이 기분 좋게 흔들려요 💛" : "유대감이 올랐어요 💛");
        e.Handled = true;
    }

    private void Window_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        if (e.ClickCount > 1) return;
        _dragging = true;
        try { DragMove(); }
        finally { _dragging = false; Settings.LastLeft = Left; Settings.LastTop = Top; }
    }

    private void Window_MouseLeftButtonUp(object sender, MouseButtonEventArgs e)
    {
        _dragging = false;
        ReleaseMouseCapture();
        Settings.LastLeft = Left; Settings.LastTop = Top;
    }

    private void Window_MouseWheel(object sender, MouseWheelEventArgs e)
    {
        Settings.Scale = Clamp(Settings.Scale + (e.Delta > 0 ? .05 : -.05), .2, 1.35);
        ApplySettings(Settings);
        ShowSpeech($"크기 {(int)(Settings.Scale * 100)}%");
    }

    private void Feed_Click(object sender, RoutedEventArgs e)
    {
        Settings.Fullness = Clamp(Settings.Fullness + 22, 0, 100);
        Settings.Mood = Clamp(Settings.Mood + 3, 0, 100);
        _sleeping = false;
        AddCare(7, Settings.Fullness < 95 ? 3 : .5);
        StartAction(PetAction.Feeding, 2.8);
        ShowSpeech(IsEgg ? "디지타마가 영양을 흡수해요!" : "잘 먹었어요!");
    }

    private void Pet_Click(object sender, RoutedEventArgs e)
    {
        Settings.Mood = Clamp(Settings.Mood + 7, 0, 100);
        AddCare(5, 4); _sleeping = false; StartAction(PetAction.Petted, 1.7); ShowSpeech("유대감이 올랐어요 💛");
    }

    private void Play_Click(object sender, RoutedEventArgs e)
    {
        if (Settings.Energy < 12) { ShowSpeech("조금 쉬고 놀자…"); return; }
        Settings.Energy = Clamp(Settings.Energy - 10, 0, 100);
        Settings.Mood = Clamp(Settings.Mood + 15, 0, 100);
        _sleeping = false;
        AddCare(10, 5); StartAction(PetAction.Playing, 4); ShowSpeech("훈련 성공! 성장도가 올랐어요 ⚽");
    }

    private void Sleep_Click(object sender, RoutedEventArgs e)
    {
        _sleeping = !_sleeping;
        StartAction(_sleeping ? PetAction.Sleeping : (Settings.Wander && !_paused ? PetAction.Walking : PetAction.Idle));
        ShowSpeech(_sleeping ? "회복 중… Zzz" : "잘 잤다!");
    }

    private async void Evolution_Click(object sender, RoutedEventArgs e) => await TryEvolveAsync(true);
    private async void Reload_Click(object sender, RoutedEventArgs e) => await LoadCurrentDigimonAsync();

    private void Pause_Click(object sender, RoutedEventArgs e)
    {
        _paused = !_paused;
        PauseMenu.Header = _paused ? "▶ 돌아다니기 재개" : "⏸ 돌아다니기 일시정지";
        if (!_sleeping) StartAction(_paused ? PetAction.Idle : PetAction.Walking);
        ShowSpeech(_paused ? "여기 있을게!" : "다시 산책 가자!");
    }

    private void AddPet_Click(object sender, RoutedEventArgs e) => ((App)System.Windows.Application.Current).AddPet();
    private void Settings_Click(object sender, RoutedEventArgs e) => ((App)System.Windows.Application.Current).OpenSettings(this);
    private void RemovePet_Click(object sender, RoutedEventArgs e) => ((App)System.Windows.Application.Current).RemovePet(this);
    private void Hide_Click(object sender, RoutedEventArgs e) => Hide();
    private void Exit_Click(object sender, RoutedEventArgs e) => ((App)System.Windows.Application.Current).ExitApp();

    private void Window_Closing(object? sender, CancelEventArgs e)
    {
        if (AllowClose) return;
        e.Cancel = true;
        Hide();
    }

    private static double Clamp(double value, double min, double max) => Math.Max(min, Math.Min(max, value));
}
