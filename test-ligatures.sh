#!/bin/bash
# Paste into a terminal using SFMono Nerd Font with ligatures enabled.

echo "── Comparison / Equality ─────────────────────────"
printf '%s\n' \
  "  ==   !=   ===   !==   >=   <=   <=>"

echo ""
echo "── Arrows ────────────────────────────────────────"
printf '%s\n' \
  "  ->   =>   -->   ==>   ->>" \
  "  <-   <--  <==   <<-   ->>" \
  "  ~>   ~~>  <~    <~~"

echo ""
echo "── Logic / Boolean ───────────────────────────────"
printf '%s\n' \
  "  ||   &&   |>    <|>"

echo ""
echo "── Comments / Slashes ────────────────────────────"
printf '%s\n' \
  "  //   /*   */   <!--   -->"

echo ""
echo "── Dots / Colons ─────────────────────────────────"
printf '%s\n' \
  "  ..   ...  ::   :::"

echo ""
echo "── Functional / Haskell ──────────────────────────"
printf '%s\n' \
  "  <\$>  <\$   \$>   <*>  <*   *>" \
  "  <+>  <+   +>   </>  <==>"

echo ""
echo "── ML / Bracket operators ────────────────────────"
printf '%s\n' \
  "  [<]  [>]  [||]  {|}  [|]"

echo ""
echo "── Python ────────────────────────────────────────"
cat << 'PYTHON'
  x, y = 10, 20
  if x == y and x != 0: pass
  if x >= 10 or y <= 100: pass
  result = lambda x: x * 2
  ok = is_valid() or not is_empty()
PYTHON

echo ""
echo "── JavaScript ────────────────────────────────────"
cat << 'JS'
  const double = x => x * 2
  const ok = isValid() && isReady() || isFallback()
  if (a !== b && c === d) console.log("match")
  const merged = { ...defaults, ...overrides }
JS

echo ""
echo "── Haskell ───────────────────────────────────────"
cat << 'HS'
  fmap :: (a -> b) -> f a -> f b
  result = (+1) <$> xs
  filtered = filter (>= 0) . map (*2) $ xs
HS

echo ""
echo "── Rust ──────────────────────────────────────────"
cat << 'RUST'
  fn add(a: i32, b: i32) -> i32 { a + b }
  let v = vec![1,2,3].iter()
      .filter(|&&x| x >= 2)
      .map(|&x| x * 2)
      .collect::<Vec<_>>();
  if ok && !done || retry { /* ... */ }
RUST
