# geoassert demo — run with: vhs demo/demo.tape

Output demo/demo.gif

Require geoassert

Set Shell zsh
Set WorkDir /Users/martenreichow/Documents/src/geoassert
Set FontSize 14
Set Width 900
Set Height 560
Set Theme "Catppuccin Mocha"
Set Padding 16
Set Framerate 24
Set PlaybackSpeed 0.8

Sleep 500ms

# --- profile ----------------------------------------------------------------
Type "geoassert profile data/buildings.parquet"
Sleep 600ms
Enter
Sleep 3s

Sleep 2s

# --- validate (passing) -----------------------------------------------------
Type "geoassert validate data/buildings.parquet --contract contracts/buildings.yml"
Sleep 600ms
Enter
Sleep 3s

# Hold on the passing result
Sleep 3s
