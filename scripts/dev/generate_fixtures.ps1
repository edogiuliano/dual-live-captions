$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$fixtureRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\tests\audio_samples'))
New-Item -ItemType Directory -Force -Path $fixtureRoot | Out-Null
$cases = @(
    @{id='english'; language='en'; voice='Microsoft Zira Desktop'; text='Good morning, how can I help you? I would like to schedule an appointment for tomorrow. Let me check our availability.'},
    @{id='spanish'; language='es'; voice='Microsoft Sabina Desktop'; text='Hola, llamo porque necesito un turno médico. Perfecto, para qué especialidad necesita el turno. Mañana por la tarde está bien.'},
    @{id='short_en'; language='en'; voice='Microsoft Zira Desktop'; text='Sure, let me check.'},
    @{id='short_es'; language='es'; voice='Microsoft Sabina Desktop'; text='Muchas gracias por su ayuda.'},
    @{id='fast_en'; language='en'; voice='Microsoft Zira Desktop'; text='Good morning.'},
    @{id='fast_es'; language='es'; voice='Microsoft Sabina Desktop'; text='Buenos días.'}
)
foreach ($case in $cases) {
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $synth.SelectVoice($case.voice)
    $synth.Rate = 0
    $synth.SetOutputToWaveFile((Join-Path $fixtureRoot ($case.id + '.wav')))
    $synth.Speak($case.text)
    $synth.Dispose()
}
$cases | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $fixtureRoot 'reference.json') -Encoding utf8
