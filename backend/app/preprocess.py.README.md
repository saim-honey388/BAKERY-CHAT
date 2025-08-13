# Preprocessing Module

## Overview

The `preprocess.py` module handles text normalization, intent detection, and spell correction for user queries. It prepares raw user input for processing by the rest of the RAG pipeline.

## Key Features

- **Text Normalization**: Cleans and standardizes user input
- **Intent Detection**: Classifies queries into categories (general_info, menu, order)
- **Spell Correction**: Corrects common misspellings of bakery product names
- **Preprocessing Pipeline**: Combines all preprocessing steps

## Components

### Text Normalization
Normalizes user input by:
- Converting to lowercase
- Removing extra whitespace
- Stripping non-informative characters while preserving punctuation

### Intent Detection
Classifies queries using keyword matching:
- **General Info**: Hours, location, contact, about, services
- **Menu**: Products, prices, availability, recommendations
- **Order**: Placing, tracking, changing, delivery, pickup

### Spell Correction
Corrects common misspellings of bakery products:
- baguette, croissant, muffin, sourdough, bread
- cake, pastry, cookie, donut, danish, scone
- bagel, roll, bun, loaf, sandwich, pie, tart

## Usage

```python
from backend.app.preprocess import Preprocessor

preprocessor = Preprocessor()
result = preprocessor.preprocess_query("What are your ours?")

# Result contains:
# - original: "What are your ours?"
# - normalized: "what are your ours"
# - corrected: "what are your hours"
# - intent: "general_info"
```

## Methods

### `normalize_text(text)`
Normalizes input text for consistency.

### `detect_intent(text)`
Determines the intent category of a query.

### `spell_correct_products(text)`
Corrects spelling of common bakery product names.

### `preprocess_query(query)`
Complete preprocessing pipeline that returns all metadata.

## Dependencies

- `re`: Regular expressions for text processing