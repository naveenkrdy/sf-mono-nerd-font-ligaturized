# SF Mono Nerd Font + Fira Code Ligatures

Patches SF Mono with Nerd Font glyphs (step 1) then injects Fira Code `calt` ligatures (step 2).

Built with **Fira Code v6.002** and **Nerd Fonts 3.4.0** — includes all v6 ligatures (`<$>`, `<*>`, `<~~`, `~~>`, `[<]`, `[>]`, `</>`, `<==>`, etc.) and the full Nerd Fonts v3 glyph set.

## Ligature samples

Set your terminal font to **SFMono Nerd Font** and enable ligatures, then paste these:

```python
# Comparison / equality
if x == y and a != b: pass
if score >= 100 or rank <= 1: pass
```

```javascript
// Arrows
const double = x => x * 2
fetch(url).then(res => res.json()).then(data => console.log(data))
```

```javascript
// Logic / comments
const ok = isValid() && isReady() || isFallback()
// single line   /* block */   <!-- html -->
```

```haskell
-- Functional operators
fmap :: (a -> b) -> f a -> f b
result = f <$> x <*> y
```

```elixir
# Pipe / arrows
"hello" |> String.upcase() |> IO.puts()
x <~ stream
```

```python
# Dots / colons
def func(*args): ...
std::vector<int> v;
```

**Enable ligatures:**
- **Terminal.app** — Preferences → Profiles → Text → Font → SFMono Nerd Font → ✓ Use ligatures
- **iTerm2** — Preferences → Profiles → Text → ✓ Use ligatures → font SFMono Nerd Font
- **VS Code** — `"editor.fontFamily": "SFMono Nerd Font"`, `"editor.fontLigatures": true`

## Prerequisites

```bash
# Step 1 — Nerd Font patcher requires FontForge
brew install fontforge

# Step 2 — Ligature patcher requires fontTools
pip3 install fonttools
```

## Step 1 — Nerd Font patch

Download the Nerd Fonts patcher and run it on every SF Mono weight:

```bash
# Download font-patcher (one-time)
curl -LO https://raw.githubusercontent.com/ryanoasis/nerd-fonts/master/font-patcher
curl -LO https://github.com/ryanoasis/nerd-fonts/raw/master/src/glyphs/FontAwesome.otf
curl -LO https://github.com/ryanoasis/nerd-fonts/raw/master/src/glyphs/Symbols-2048-em Nerd Font Complete.ttf
# Or clone the full repo for the complete glyph set:
# git clone --depth 1 https://github.com/ryanoasis/nerd-fonts

mkdir -p fonts/nerd-otf

for f in fonts/SF-Mono-*.otf; do
    fontforge -script font-patcher "$f" \
        --complete \
        --outputdir fonts/nerd-otf/ \
        --no-progressbars \
        2>/dev/null
done
```

The patcher renames files (e.g. `SF-Mono-Regular.otf` → `SFMonoNerdFont-Regular.otf`) and places them in `fonts/nerd-otf/`.

> **Already done:** `fonts/nerd-otf/` already contains the patched files. Only re-run this if you want to rebuild from the original SF Mono OTFs.

## Step 2 — Inject Fira Code ligatures

```bash
python3 patch.py
```

Reads from `fonts/nerd-otf/`, outputs to `fonts/final/`. Processes all 12 weight/style pairs.

## Step 3 — Install

```bash
cp fonts/final/SFMonoNerdFont-*.otf ~/Library/Fonts/
atsutil databases -removeUser   # clear macOS font cache
```

Then select **SFMono Nerd Font** in your editor with ligatures enabled.

## Verify ligatures

```bash
# Requires: brew install harfbuzz
FONT=fonts/final/SFMonoNerdFont-Regular.otf
for seq in "==" "!=" ">=" "<=" "=>" "===" "!==" "->" "--" "->>" "||" "&&" "..." "<>" "<|>"; do
    echo -n "$seq: "
    hb-shape "$FONT" --text="$seq"
done
```

## Font sources

- `fonts/SF-Mono-*.otf` — extracted from Xcode or the SF Mono package
- `fonts/FiraCode-*.ttf` — [Fira Code v6.002](https://github.com/tonsky/FiraCode/releases/tag/6.2) (TTF, all weights)
- `fonts/nerd-otf/` — output of step 1, patched with [Nerd Fonts 3.4.0](https://github.com/ryanoasis/nerd-fonts/releases/tag/v3.4.0)
- `fonts/final/` — output of step 2 (final fonts to install)

## Weight mapping

| SF Mono weight | Fira Code source |
|---|---|
| Light, LightItalic | FiraCode-Light |
| Regular, Italic | FiraCode-Regular |
| Medium, MediumItalic | FiraCode-Medium |
| SemiBold, SemiBoldItalic | FiraCode-SemiBold |
| Bold, BoldItalic, Heavy, HeavyItalic | FiraCode-Bold |
