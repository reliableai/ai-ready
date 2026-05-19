# Sources of Uncertainty in AI Evaluation - PowerPoint Presentation

## Overview

A comprehensive 48-slide PowerPoint presentation for Master's students on "Sources of Uncertainty in AI Evaluation." Designed for the course "Designing Large Scale AI Systems" at University of Trento, Spring 2026.

## Files

- **sources_of_uncertainty.pptx** (94 KB) - Main presentation file
- **sources_of_uncertainty.pdf** (221 KB) - PDF export for printing/sharing
- **slide-01.jpg through slide-48.jpg** - Individual slide images at 150 DPI

## Content Summary

### Slides 1-3: Opening
- Title slide with course branding
- The Setup: Unified evaluation scenario with 4-metric scorecard
- Overview of 9 sources + judge layer

### Slides 4-33: Nine Sources of Uncertainty
Each source gets 3-4 dedicated slides following a consistent pattern:

1. **Sampling Noise** (Slides 4-7) - Variance at small n
2. **Sampling Bias** (Slides 8-11) - Wrong population distribution
3. **Overfitting** (Slides 12-15) - Information leakage during optimization
4. **Multiple Hypothesis Testing** (Slides 16-20) - Selection bias
5. **Variance Across Domains** (Slides 21-24) - Simpson's paradox
6. **Choice of Metric** (Slides 25-27) - Design decision, not discovery
7. **Temporal Drift** (Slides 28-30) - World changes after evaluation
8. **Prompt Brittleness** (Slides 31-34) - Sensitivity to wording
9. **LLM Evolution** (Slides 35-37) - Model updates break assumptions

### Slides 38-41: The Judge Layer
Judge as a cross-cutting uncertainty multiplier - every source applies again at the measurement level.

### Slides 42-46: Capstone - Uncertainty Compounds
- Stacking table showing how uncertainty grows
- Anti-intuitions students need to unlearn
- The key takeaway message
- Summary of "does more data help?"

### Slides 47-48: Closing
- Interactive tools and playgrounds
- Final philosophical quote

## Design

**Color Palette** (Midnight/Dark Theme):
- Dark Navy #1E2761 - Backgrounds
- Lighter Navy #263069 - Content slides
- White #FFFFFF - Titles
- Ice Blue #CADCFC - Body text
- Accent colors by metric: Blue, Orange, Green, Purple
- Red for judge layer, Yellow for warnings

**Typography**:
- Titles: Calibri Bold, 36-40pt, white
- Body: Calibri, 14-18pt, ice blue
- Labels: Calibri, 10-14pt, muted

**Layout**:
- 16:9 widescreen (10" x 5.625")
- Visual elements on every slide
- Consistent section dividers
- Slide numbers (bottom right, 10pt, muted)

## Pedagogical Features

**Pattern for Each Source**:
1. Feel it - Visceral moment showing how students get fooled
2. Fix it - Practical remedies and mitigations
3. Does more data help? - Answers for each source

**Key Takeaway**:
> "The scorecard is not a measurement of your system. It's a measurement of your system as seen by this judge, with this prompt, on this data, at this moment in time."

## Usage

### Opening the Presentation
- **PowerPoint**: Open sources_of_uncertainty.pptx
- **PDF**: sources_of_uncertainty.pdf (for printing)
- **Web**: Display slide-XX.jpg images individually

### Teaching Notes
- Each source includes problem → fix → deeper analysis
- Interactive playgrounds referenced separately (HTML files)
- Live demos suggested for sources #3, #8, #9
- Judge layer builds conceptually on sources #1-9
- Capstone reinforces anti-intuitions for student learning

### For Instructors
- No locked slide timings (you pace)
- Empty notes pages (add speaker notes as needed)
- All standard fonts (no special requirements)
- Content designed for narrative-driven presentation
- Can pause for discussion and interactive exploration

## Technical Details

**Created with**: Python 3 + python-pptx library
**Format**: Microsoft OOXML (PowerPoint 2007+)
**Compatibility**: PowerPoint, Google Slides, LibreOffice
**File Size**: 94 KB (PPTX), highly optimized

## Quality Assurance

All 48 slides have been:
- Visually inspected for color accuracy and readability
- Verified for consistent typography and layout
- Checked for content accuracy against design document
- Tested for proper slide number placement
- Confirmed for visual element integration

## Key Concepts

### The Nine Sources

| # | Source | Fix | More Data? |
|---|--------|-----|-----------|
| 1 | Sampling Noise | CI, bootstrap | YES |
| 2 | Sampling Bias | Stratified sampling | NO |
| 3 | Overfitting | Train/dev/test discipline | PARTIAL |
| 4 | Multiple Hypothesis Testing | Two-stage evaluation | PARTIAL |
| 5 | Variance Across Domains | Per-segment reporting | NO |
| 6 | Choice of Metric | Pre-commitment | NO |
| 7 | Temporal Drift | Continuous monitoring | NO |
| 8 | Prompt Brittleness | Sensitivity testing | NO |
| 9 | LLM Evolution | Version pinning | NO |

### The Judge Layer

Judges (LLM or human) are noisy, biased, subjective, brittle, and evolving. Every measurement passes through the judge, so judge problems compound with all other sources.

### Uncertainty Compounds

Uncertainties add (variances sum), they don't cancel. A very precise wrong number is worse than a vague right one.

## References

- Chen et al. (2023) "How Is ChatGPT's Behavior Changing over Time?"
- Zhao et al. (2021) "Calibrate Before Use"
- Deepchecks production analysis on LLM evaluation
- Research on prompt brittleness and model sensitivity

## Contact

For questions about this presentation, refer to the course materials or syllabus.

---

**Last Updated**: April 9, 2026  
**Status**: Complete and classroom-ready
