using System.Windows;

namespace GorapaduckPet;

public partial class SettingsWindow : Window
{
    public PetSettings Result { get; private set; }

    public SettingsWindow(PetSettings current)
    {
        InitializeComponent();
        Result = current.Copy();
        ScaleSlider.Value = Result.Scale;
        SpeedSlider.Value = Result.Speed;
        WanderCheck.IsChecked = Result.Wander;
        TopmostCheck.IsChecked = Result.AlwaysOnTop;
        FullscreenCheck.IsChecked = Result.HideForFullscreen;
        UpdateLabels();
    }

    private void Slider_ValueChanged(object sender, RoutedPropertyChangedEventArgs<double> e) => UpdateLabels();

    private void UpdateLabels()
    {
        if (ScaleLabel is null || SpeedLabel is null) return;
        ScaleLabel.Text = $"{ScaleSlider.Value:P0}";
        SpeedLabel.Text = $"{SpeedSlider.Value:0.0}";
    }

    private void Save_Click(object sender, RoutedEventArgs e)
    {
        Result.Scale = ScaleSlider.Value;
        Result.Speed = SpeedSlider.Value;
        Result.Wander = WanderCheck.IsChecked == true;
        Result.AlwaysOnTop = TopmostCheck.IsChecked == true;
        Result.HideForFullscreen = FullscreenCheck.IsChecked == true;
        DialogResult = true;
    }
}
