#!/usr/bin/env python3
"""
Patch SF Mono Nerd Font OTFs with Fira Code calt ligatures.

For each weight pair:
  1. Collect glyph names that Fira Code's calt lookups reference as outputs.
  2. Copy those glyphs into the target CFF:
       - Spacer/zero-width glyphs: add empty charstrings.
       - Ligature/alternate glyphs: convert TTF glyf -> CFF via Qu2CuPen.
  3. Inject the calt GSUB lookups (fully decompiled before copy):
       - Strip missing glyph references from Coverage arrays post-injection.
       - Offset all embedded SubstLookupRecord indices.
  4. Wire calt into DFLT and latn DefaultLangSys.
"""

import copy
import sys
from pathlib import Path

from fontTools.misc.psCharStrings import T2CharString
from fontTools.pens.qu2cuPen import Qu2CuPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables

FONTS_DIR = Path("fonts")
NERD_DIR = FONTS_DIR / "nerd-otf"
OUT_DIR = FONTS_DIR / "final"

WEIGHT_MAP = [
    ("FiraCode-Light.ttf",    "SFMonoNerdFont-Light.otf"),
    ("FiraCode-Light.ttf",    "SFMonoNerdFont-LightItalic.otf"),
    ("FiraCode-Regular.ttf",  "SFMonoNerdFont-Regular.otf"),
    ("FiraCode-Regular.ttf",  "SFMonoNerdFont-Italic.otf"),
    ("FiraCode-Medium.ttf",   "SFMonoNerdFont-Medium.otf"),
    ("FiraCode-Medium.ttf",   "SFMonoNerdFont-MediumItalic.otf"),
    ("FiraCode-SemiBold.ttf", "SFMonoNerdFont-SemiBold.otf"),
    ("FiraCode-SemiBold.ttf", "SFMonoNerdFont-SemiBoldItalic.otf"),
    ("FiraCode-Bold.ttf",     "SFMonoNerdFont-Bold.otf"),
    ("FiraCode-Bold.ttf",     "SFMonoNerdFont-BoldItalic.otf"),
    ("FiraCode-Bold.ttf",     "SFMonoNerdFont-Heavy.otf"),
    ("FiraCode-Bold.ttf",     "SFMonoNerdFont-HeavyItalic.otf"),
]

# ---------------------------------------------------------------------------
# Lookup graph traversal
# ---------------------------------------------------------------------------

def _calt_seed(gsub):
    for fr in gsub.FeatureList.FeatureRecord:
        if fr.FeatureTag == "calt":
            return list(fr.Feature.LookupListIndex)
    return []


def _follow_subst_records(sub):
    """Yield all LookupListIndex values embedded in SubstLookupRecords."""
    for lr in getattr(sub, "SubstLookupRecord", []):
        yield lr.LookupListIndex
    # Format 1: ChainSubRuleSet -> ChainSubRule -> SubstLookupRecord
    for rss in getattr(sub, "ChainSubRuleSet", None) or []:
        if not rss:
            continue
        for rule in getattr(rss, "ChainSubRule", []):
            for lr in getattr(rule, "SubstLookupRecord", []):
                yield lr.LookupListIndex


def transitive_indices(gsub, seed):
    """Return the set of all lookup indices reachable from seed via SubstLookupRecords."""
    seen = set()
    queue = list(seed)
    while queue:
        idx = queue.pop()
        if idx in seen:
            continue
        seen.add(idx)
        lk = gsub.LookupList.Lookup[idx]
        lk.ensureDecompiled(recurse=True)
        for sub in lk.SubTable:
            for child_idx in _follow_subst_records(sub):
                queue.append(child_idx)
    return seen


def collect_output_glyphs(gsub, all_indices):
    """Return glyph names that appear as substitution OUTPUTS in these lookups."""
    outputs = set()
    for idx in all_indices:
        lk = gsub.LookupList.Lookup[idx]
        for sub in lk.SubTable:
            if hasattr(sub, "mapping"):
                for v in sub.mapping.values():
                    if isinstance(v, list):      # Type 2 MultipleSubst
                        outputs.update(v)
                    else:                        # Type 1 SingleSubst
                        outputs.add(v)
            if hasattr(sub, "ligatures"):        # Type 4 LigatureSubst
                for ligs in sub.ligatures.values():
                    for lig in ligs:
                        outputs.add(lig.LigGlyph)
    return outputs

# ---------------------------------------------------------------------------
# Glyph addition
# ---------------------------------------------------------------------------

def _append_glyph(dst, name, width, charstring):
    cff_top = dst["CFF "].cff.topDictIndex[0]
    cs = cff_top.CharStrings
    if name in cs.charStrings:
        cs[name] = charstring                          # update existing
    elif cs.charStringsAreIndexed:
        new_idx = len(cs.charStringsIndex.items)
        cs.charStrings[name] = new_idx
        charstring.private = cff_top.Private           # required for width encoding
        cs.charStringsIndex.items.append(charstring)
    else:
        cs.charStrings[name] = charstring
    dst["hmtx"].metrics[name] = (width, 0)
    order = dst.getGlyphOrder()
    if name not in order:
        order.append(name)
        dst.setGlyphOrder(order)


def add_empty_glyph(dst, name, width=0):
    cs = T2CharString()
    cs.program = ["endchar"]
    _append_glyph(dst, name, width, cs)


def copy_glyph_ttf_to_cff(src, dst, name):
    """Convert a glyph from src's glyf table into a CFF T2CharString in dst."""
    src_gs = src.getGlyphSet()
    if name not in src_gs:
        return False
    width = src["hmtx"].metrics[name][0]
    cs_pen = T2CharStringPen(width, src_gs)
    qu2cu = Qu2CuPen(cs_pen, max_err=1.0, all_cubic=False)
    try:
        src_gs[name].draw(qu2cu)
        cs = cs_pen.getCharString()
    except Exception as exc:
        print(f"    [warn] {name}: outline conversion failed ({exc}), using empty stub")
        add_empty_glyph(dst, name, width)
        return True
    _append_glyph(dst, name, width, cs)
    return True

# ---------------------------------------------------------------------------
# GSUB lookup copying and renumbering
# ---------------------------------------------------------------------------

def copy_lookup(src_lk):
    """Fully decompile and deep-copy a lookup so filters see real Python objects."""
    src_lk.ensureDecompiled(recurse=True)
    return copy.deepcopy(src_lk)


def renumber_lookup(lk, index_map):
    """Rewrite all embedded SubstLookupRecord indices using index_map in-place."""
    for sub in lk.SubTable:
        for lr in getattr(sub, "SubstLookupRecord", []):
            lr.LookupListIndex = index_map[lr.LookupListIndex]
        for rss in getattr(sub, "ChainSubRuleSet", None) or []:
            if not rss:
                continue
            for rule in getattr(rss, "ChainSubRule", []):
                for lr in getattr(rule, "SubstLookupRecord", []):
                    lr.LookupListIndex = index_map[lr.LookupListIndex]

# ---------------------------------------------------------------------------
# Post-injection coverage cleanup
# ---------------------------------------------------------------------------

def _strip_coverage(cov, dst_set):
    """Remove missing glyphs from a Coverage object in-place."""
    if hasattr(cov, "glyphs"):
        cov.glyphs = [g for g in cov.glyphs if g in dst_set]


def _strip_classdef(classdef, dst_set):
    """Remove entries for missing glyphs from a ClassDef in-place."""
    if hasattr(classdef, "classDefs"):
        classdef.classDefs = {
            g: cls for g, cls in classdef.classDefs.items()
            if g in dst_set
        }


def strip_missing_glyph_refs(gsub, from_idx, dst_set):
    """
    After injecting new lookups starting at from_idx, remove all references to
    glyphs absent from dst_set.  Covers:
      - Format 3 BacktrackCoverage / InputCoverage / LookAheadCoverage
      - Format 2 BacktrackClassDef / InputClassDef / LookAheadClassDef
      - Format 1 ChainSubRuleSet -> ChainSubRule Backtrack/Input/LookAhead sequences
      - Type 1/2/4 substitution mapping/ligature entries
    """
    for lk in gsub.LookupList.Lookup[from_idx:]:
        lt = lk.LookupType
        for sub in lk.SubTable:
            # Format 3: Coverage arrays directly on subtable
            for attr in ("BacktrackCoverage", "InputCoverage", "LookAheadCoverage"):
                for cov in getattr(sub, attr, []) or []:
                    _strip_coverage(cov, dst_set)
            if hasattr(sub, "Coverage"):
                _strip_coverage(sub.Coverage, dst_set)

            # Format 2: ClassDef objects (class-based chained context)
            for attr in ("BacktrackClassDef", "InputClassDef", "LookAheadClassDef",
                         "ClassDef"):
                cd = getattr(sub, attr, None)
                if cd is not None:
                    _strip_classdef(cd, dst_set)

            # Format 1: ChainSubRuleSet -> ChainSubRule
            for rss in getattr(sub, "ChainSubRuleSet", None) or []:
                if not rss:
                    continue
                new_rules = []
                for rule in getattr(rss, "ChainSubRule", []):
                    ctx = (
                        list(getattr(rule, "Backtrack", []))
                        + list(getattr(rule, "Input", []))
                        + list(getattr(rule, "LookAhead", []))
                    )
                    if all(g in dst_set for g in ctx):
                        new_rules.append(rule)
                rss.ChainSubRule = new_rules

            # Type 1 SingleSubst
            if lt == 1 and hasattr(sub, "mapping"):
                sub.mapping = {
                    k: v for k, v in sub.mapping.items()
                    if k in dst_set and (
                        (isinstance(v, list) and all(g in dst_set for g in v))
                        or (isinstance(v, str) and v in dst_set)
                    )
                }

            # Type 2 MultipleSubst
            if lt == 2 and hasattr(sub, "mapping"):
                sub.mapping = {
                    k: v for k, v in sub.mapping.items()
                    if k in dst_set and all(g in dst_set for g in v)
                }

            # Type 4 LigatureSubst
            if lt == 4 and hasattr(sub, "ligatures"):
                new_ligs = {}
                for first, ligs in sub.ligatures.items():
                    if first not in dst_set:
                        continue
                    valid = [
                        lig for lig in ligs
                        if all(c in dst_set for c in lig.Component)
                        and lig.LigGlyph in dst_set
                    ]
                    if valid:
                        new_ligs[first] = valid
                sub.ligatures = new_ligs

# ---------------------------------------------------------------------------
# GSUB feature wiring
# ---------------------------------------------------------------------------

def _get_or_create_calt_feature(gsub, new_lookup_indices):
    fl = gsub.FeatureList
    for i, fr in enumerate(fl.FeatureRecord):
        if fr.FeatureTag == "calt":
            fr.Feature.LookupListIndex.extend(new_lookup_indices)
            return i
    feat = otTables.Feature()
    feat.FeatureParams = None
    feat.LookupListIndex = list(new_lookup_indices)
    fr = otTables.FeatureRecord()
    fr.FeatureTag = "calt"
    fr.Feature = feat
    fl.FeatureRecord.append(fr)
    feat_idx = len(fl.FeatureRecord) - 1
    fl.FeatureCount = len(fl.FeatureRecord)
    return feat_idx


def wire_calt_to_scripts(gsub, feat_idx):
    for sr in gsub.ScriptList.ScriptRecord:
        if sr.ScriptTag in ("DFLT", "latn"):
            dls = sr.Script.DefaultLangSys
            if dls and feat_idx not in dls.FeatureIndex:
                dls.FeatureIndex.append(feat_idx)

# ---------------------------------------------------------------------------
# Main injection routine
# ---------------------------------------------------------------------------

def inject_calt(src, dst):
    src_gsub = src["GSUB"].table
    dst_gsub = dst["GSUB"].table

    seed = _calt_seed(src_gsub)
    if not seed:
        print("  [skip] no calt in source")
        return

    all_indices = transitive_indices(src_gsub, seed)
    sorted_indices = sorted(all_indices)

    # --- Step 1: add missing output glyphs to dst ---
    output_glyphs = collect_output_glyphs(src_gsub, all_indices)
    dst_glyph_set = set(dst.getGlyphOrder())
    missing_outputs = output_glyphs - dst_glyph_set

    src_hmtx = src["hmtx"].metrics
    added_empty = added_outline = 0
    for name in sorted(missing_outputs):
        width = src_hmtx.get(name, (0, 0))[0]
        if width == 0 or name.endswith(".spacer"):
            add_empty_glyph(dst, name, width)
            added_empty += 1
        else:
            if copy_glyph_ttf_to_cff(src, dst, name):
                added_outline += 1
            else:
                add_empty_glyph(dst, name, width)
                added_empty += 1
    print(f"  glyphs added: {added_outline} with outlines, {added_empty} empty stubs")

    dst_glyph_set = set(dst.getGlyphOrder())

    # --- Step 2: copy, renumber, and append lookups ---
    offset = len(dst_gsub.LookupList.Lookup)
    index_map = {old: offset + i for i, old in enumerate(sorted_indices)}

    for old_idx in sorted_indices:
        lk = copy_lookup(src_gsub.LookupList.Lookup[old_idx])
        renumber_lookup(lk, index_map)
        dst_gsub.LookupList.Lookup.append(lk)

    print(f"  lookups injected: {len(sorted_indices)} total")

    # --- Step 3: strip any remaining references to missing glyphs ---
    strip_missing_glyph_refs(dst_gsub, offset, dst_glyph_set)

    # --- Step 4: wire calt feature ---
    active_calt_indices = [index_map[i] for i in seed]
    feat_idx = _get_or_create_calt_feature(dst_gsub, active_calt_indices)
    wire_calt_to_scripts(dst_gsub, feat_idx)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def patch_pair(fc_path, sf_path):
    print(f"\n{fc_path.name} -> {sf_path.name}")
    src = TTFont(fc_path)
    dst = TTFont(sf_path)
    inject_calt(src, dst)
    out_path = OUT_DIR / sf_path.name
    dst.save(str(out_path))
    print(f"  saved -> {out_path}")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for fc_name, sf_name in WEIGHT_MAP:
        fc_path = FONTS_DIR / fc_name
        sf_path = NERD_DIR / sf_name
        if not fc_path.exists():
            print(f"[skip] {fc_path} not found")
            continue
        if not sf_path.exists():
            print(f"[skip] {sf_path} not found")
            continue
        try:
            patch_pair(fc_path, sf_path)
        except Exception as exc:
            print(f"  [ERROR] {exc}", file=sys.stderr)
            raise


if __name__ == "__main__":
    main()
