# Scoutr Frontend Spec

This file describes the current frontend, not the earlier dark chat prototype.

## Direction

Scoutr currently uses a playful light-theme product browser with hand-drawn shapes, bold borders, and tier tabs. The experience is built around showing three products at a time inside one selected tier, plus a compact comparison table underneath.

## Visual System

- Background: warm off-white with white cards
- Typography: `Comic Neue`
- Accent colors:
  - `cost_effective`: green
  - `basic`: teal
  - `premium`: coral red
  - `lavish`: purple
- Surfaces use thick dark borders and offset shadows instead of subtle elevation

## Layout

- Sticky top navigation with logo and Home button
- Centered hero search section
- Loading state with staged progress messages
- Results view with:
  - intro card
  - tier tabs
  - three-card product grid
  - comparison table
  - secondary search bar

## Product Card Requirements

Each card should show:

- product image when available
- name
- current price
- optional original price and savings badge
- tagline
- three key specs
- short explanation
- Amazon CTA
- eBay, Walmart, and Google fallback links when present

## Interaction Rules

- Enter submits from both search inputs
- Example chips copy text into the hero input
- Switching tabs rerenders the product grid and comparison table
- Image failures should degrade cleanly without breaking the card layout

## Responsive Behavior

- Mobile: one product card per row, wrapped tier tabs
- Tablet: two cards per row
- Desktop: three cards per row

## Source of Truth

If this document and `index.html` disagree, treat `index.html` as the current implementation and update this file to match.
