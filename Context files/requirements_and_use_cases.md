# Application Requirements & Use Cases
**Transparent Multi-Objective Food Recommendations Platform**

---

## Functional Requirements

**FR-01 — Product Search**
The system shall allow the user to search for a food product by name. Search results must be returned without requiring registration or login.

**FR-02 — Multi-Criteria Filtering**
The system shall allow filtering products by nutritional criteria (high protein, low sugar, no artificial sweeteners) and ecological criteria (low CO₂, local origin, organic).

**FR-03 — Priority Slider**
The system shall provide a slider for the user to set a personal weight between health and ecological impact (e.g. 70% health / 30% eco). The default value is 70/30 in favour of health, reflecting user research findings (6 out of 8 participants prioritised health over eco).

**FR-04 — Allergen Filter**
The system shall allow the user to specify allergens as hard constraints, applied before any scoring takes place. No product containing a specified allergen may be recommended under any circumstances.

**FR-05 — Two-Alternative Recommendation**
For every searched product, the system shall automatically suggest two alternatives: one nutritionally superior ("Better for You") and one ecologically superior ("Better for Earth"). If a product scores better on both dimensions simultaneously, it is surfaced as the primary recommendation.

**FR-06 — XAI Explanation of Recommendations**
Every recommendation must be accompanied by a plain-language explanation (max. 2 sentences) stating why the product was recommended, referencing specific attributes (e.g. "Uses 80% less water while maintaining the same protein content").

**FR-07 — Radar Chart Visualisation**
The system shall display an interactive radar/spider chart comparing the searched product and its alternatives across 5–6 dimensions (Nutri-Score, Eco-Score, protein, sugar, CO₂, price).

**FR-08 — Eco-Metrics in Concrete Units**
Ecological metrics must never be displayed as abstract scores. The system shall translate them into relatable comparisons (e.g. "Grown 28 km away", "Equivalent to 0.4 km driven by car").

**FR-09 — Data Source Transparency**
The system shall display a reference to the data source (Open Food Facts database) for every piece of information used in a recommendation. This is a direct requirement from Theme 7 of the user research report.

**FR-10 — No Mandatory Registration**
Core functionality (search, recommendations, XAI explanations) must be available without registration. Registration may be offered optionally for saving user preferences across sessions.

---

## Non-Functional Requirements

**NFR-01 — Response Time**
Search results and recommendations must be displayed within 3 seconds of query submission.

**NFR-02 — Colour Accessibility**
The UI must not rely solely on colour to convey information (colour blindness affects approximately 8% of men). Every colour-coded indicator must be accompanied by an icon or text label.

**NFR-03 — Low Cognitive Load**
The main results screen must be scannable within 5 seconds without scrolling. Detailed information is available on demand via expandable sections.

**NFR-04 — No Moralising Framing**
The system must not use guilt-inducing or moralising language. Ecological improvements are always framed as gains, never as substitutions or sacrifices.

---

## Use Cases

---

### UC-01: Search for a Product and View Alternatives

**Actor:** Any user (no login required)

**Precondition:** User has the web application open.

**Main Flow:**
1. User enters a product name in the search field (e.g. "whole milk").
2. System queries the Open Food Facts database and returns the matching product.
3. System calculates a combined score based on the current priority slider setting.
4. System displays three cards: the searched product, the "Better for You" alternative, and the "Better for Earth" alternative.
5. Each card shows eco-metrics in concrete units and a plain-language explanation.

**Alternative Flow:** Product not found in the database → system displays a message and suggests similar products.

---

### UC-02: Adjust the Priority Slider

**Actor:** Any user

**Precondition:** User is viewing search results.

**Main Flow:**
1. User moves the slider from the default 70/30 to a different setting (e.g. 40% health / 60% eco).
2. System immediately recalculates scores and re-ranks alternatives.
3. The displayed recommendation updates without requiring a new search.

---

### UC-03: Set an Allergen as a Hard Constraint

**Actor:** User with a food allergy (corresponds to persona Simon Joen — Value-Driven Traditionalist)

**Precondition:** User has opened the filter/settings panel.

**Main Flow:**
1. User enters one or more allergens (e.g. walnuts, hazelnuts).
2. System stores the constraint for the current session.
3. For all subsequent recommendations, the system automatically excludes products containing the specified allergen — this rule cannot be overridden by any score.

---

### UC-04: Read the XAI Explanation and Verify the Source

**Actor:** User with low trust in AI recommendations (corresponds to persona Maya Kolsky — Eco-Beginner)

**Precondition:** User is viewing a recommendation.

**Main Flow:**
1. User sees a recommendation and wants to understand why it was made.
2. User clicks "Why is this recommended?".
3. System displays: (a) a one-sentence plain-language summary, (b) a radar chart across 5–6 dimensions, (c) an expandable detail section with specific figures and a link to the Open Food Facts source.
4. User can verify the data on the external source.

**Alternative Flow:** User disagrees with the recommendation → adjusts the priority slider → recommendation is recalculated.

---

### UC-05: Quick Comparison Without Reading Details

**Actor:** Time-constrained user (corresponds to persona Adrien Dawin — Fitness Pragmatist)

**Precondition:** User has searched for a product.

**Main Flow:**
1. User searches for a product.
2. User reads only the colour-coded cards with the three products (skim reading).
3. User makes a decision based on the icon and number visible on the card without opening any detail view.
4. The system supports this flow — the detail view is optional, not a required step.
