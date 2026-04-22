# Creating Representations of Things - Slide Deck Outline

Status: first draft. This file is the working outline for a lecture/deck on
how AI and data systems turn real-world objects into representations that make
useful questions computable.

## Core Framing

Representations are useful simplifications. We choose a way to encode a
"thing" - a word, user, product, document, image, song, city, transaction, or
company - so that operations on the representation answer questions we care
about:

- Which things are similar?
- Which things are different?
- What should we recommend next?
- Which examples belong together?
- Which examples are unusual?
- Can we predict a missing property from nearby examples?

The central teaching move:

> A representation is not a neutral mirror of reality. It is a choice about
> which differences matter for a task.

## Target Learning Outcomes

By the end, students should be able to:

1. Explain why we create representations of "things" before applying AI or
   analytics.
2. Distinguish hand-designed features, learned embeddings, and latent factors.
3. Explain similarity as distance or angle in a representation space.
4. Use representations of words, users, and products to solve retrieval,
   clustering, recommendation, and anomaly-detection problems.
5. Critique a representation by asking what it preserves, what it hides, and
   who it may fail for.

## Deck Shape

Target: 30-35 slides.

Suggested sections:

1. Creating representations of things.
2. Similarity: turning representations into questions.
3. Learning representations from behavior.
4. Recommendations as geometry.
5. Limits, failure modes, and design choices.

This draft fully expands Section 01 and sketches the rest so the deck has a
clear direction.

---

## Opener

### Slide 1 - Title

- **Creating Representations of Things**
- Words, users, products, and the geometry behind recommendations.
- Subtitle option: *How to make "similar" computable.*

### Slide 2 - The Problem

- Computers do not start with "meaning."
- They start with symbols, rows, pixels, events, and IDs.
- To answer useful questions, we need to turn things into representations.
- Example questions:
  - Are these two words related?
  - Which products are substitutes?
  - Which users have similar taste?
  - What should we recommend next?

Speaker note: start concrete. "User 4821" and "product 9917" are just IDs
until we give them useful coordinates.

### Slide 3 - The One-Slide Thesis

- A representation maps a thing into a form a system can operate on.
- Most often: a vector of numbers.
- Similar things should land near each other.
- Different tasks require different notions of "near."

Visual:

```text
thing              representation              useful operation
"espresso"   ->   [0.12, -0.41, ...]      ->   nearest words
user_42      ->   [0.88, 0.03, ...]       ->   recommended products
product_17   ->   [0.64, -0.20, ...]      ->   similar products
```

Key line:

> Representations turn vague questions into mathematical ones.

---

## Section 01 - Creating Representations Of Things

### Slide 4 - What Is A Representation?

- A representation is a useful encoding of something.
- It is not the thing itself.
- It preserves some differences and discards others.
- Good representations make downstream questions easier.

Examples:

- A map represents a city by preserving streets and distances.
- A menu represents food by preserving names, categories, and prices.
- A user profile represents a person by preserving behavior relevant to the
  product.
- An embedding represents a word by preserving patterns of use.

### Slide 5 - Representation Is A Choice

- The same thing can have many representations.
- Each representation answers some questions well and others badly.

Example: a product.

| Representation | Useful for | Weak for |
| --- | --- | --- |
| Price, category, brand | Filtering and dashboards | Taste and style |
| Text description | Search and semantic similarity | Actual user preference |
| Purchase history | Recommendations | Cold-start products |
| Image embedding | Visual similarity | Price sensitivity |

Thesis:

> There is no best representation in the abstract. There is only a
> representation that fits a question.

### Slide 6 - The Spreadsheet Version

- The simplest representation is a row in a table.
- Columns are features.
- Similarity can be computed from columns.

Example:

| Product | Price | Category | Brand | Avg rating |
| --- | ---: | --- | --- | ---: |
| A | 19.99 | headphones | X | 4.6 |
| B | 21.99 | headphones | Y | 4.5 |
| C | 999.00 | laptop | Z | 4.7 |

Question:

- Which products are similar?

Teaching point:

- With only these columns, A and B look similar.
- But this representation cannot see sound profile, style, or user intent.

### Slide 7 - From Categories To Numbers

- Models need numbers.
- We often convert categories into numeric features.
- Common choices:
  - One-hot encoding.
  - Counts.
  - Normalized numeric columns.
  - Scores from another model.

Mini example:

```text
category=headphones -> [1, 0, 0]
category=laptop     -> [0, 1, 0]
category=book       -> [0, 0, 1]
```

Warning:

- Numeric does not automatically mean meaningful.
- Encoding choices create assumptions.

### Slide 8 - The Geometry Move

- Once things are vectors, they live in a space.
- We can ask geometric questions:
  - Which vectors are closest?
  - Which clusters form?
  - Which point is far from the rest?
  - Which direction corresponds to a change we care about?

Visual:

```text
          product C

product A    product B

                         product D
```

Speaker note: do not over-teach linear algebra yet. The point is that
coordinates let us compute relationships.

### Slide 9 - Similarity Depends On The Representation

- "Similar" is not one thing.
- Two products can be similar in price but different in function.
- Two users can be similar in demographics but different in taste.
- Two words can be similar in spelling but different in meaning.

Examples:

| Question | Representation should preserve |
| --- | --- |
| "Find typos of this word" | characters and spelling |
| "Find synonyms" | meaning and usage |
| "Recommend products" | preference and behavior |
| "Detect fraud" | unusual transaction patterns |

Thesis:

> Similarity is always similarity with respect to a representation.

### Slide 10 - Words As Representations

- Old representation: dictionary definitions or one-hot word IDs.
- Problem: one-hot IDs say every word is equally unrelated to every other word.
- Better idea: represent words by the company they keep.
- Words used in similar contexts get similar vectors.

Example:

```text
"king"     near "queen", "monarch", "prince"
"espresso" near "coffee", "cappuccino", "latte"
"refund"  near "return", "chargeback", "support"
```

Speaker note: this is the bridge into embeddings without making embeddings
mysterious.

### Slide 11 - The Distributional Idea

- A word's meaning is partly revealed by its contexts.
- If two words appear in similar contexts, they likely have related meaning.
- This turns raw text into a learning signal.

Example contexts:

```text
I ordered an espresso after lunch.
I ordered a cappuccino after lunch.
I ordered a laptop after lunch.
```

Teaching beat:

- "espresso" and "cappuccino" are more interchangeable than "laptop" in this
  context.

### Slide 12 - Users As Representations

- A user can be represented by what they do.
- Examples:
  - Products viewed.
  - Products bought.
  - Searches made.
  - Videos watched.
  - Ratings given.
  - Time, device, location, session pattern.

Possible vector:

```text
user_42 = [likes_running, price_sensitive, buys_weekends, prefers_brand_X, ...]
```

Important caveat:

- This is a product-specific representation of a person, not the person.

### Slide 13 - Products As Representations

- A product can be represented by:
  - Metadata: price, brand, category, tags.
  - Text: title, description, reviews.
  - Image: visual appearance.
  - Behavior: who viewed, bought, returned, or compared it.
  - Graph: which products co-occur in baskets or sessions.

Key point:

- Content-based representations use the product itself.
- Behavioral representations use how people interact with it.

### Slide 14 - Same Product, Different Spaces

Example: a running shoe.

| Space | Nearby products |
| --- | --- |
| Price space | Other items around 120 dollars |
| Category space | Other running shoes |
| Visual space | Shoes with similar shape/color |
| Behavioral space | Items bought by the same users |
| Text space | Products described with similar language |

Question to class:

- Which space would you use for "customers also considered"?
- Which space would you use for "complete the outfit"?
- Which space would you use for "find cheaper alternatives"?

### Slide 15 - Documents, Images, Songs, Places

- The same pattern generalizes.
- Documents: topic, style, factual content, audience.
- Images: objects, colors, composition, style.
- Songs: genre, tempo, instrumentation, listening behavior.
- Places: geography, price, activities, user reviews.

Teaching point:

- Representation learning is not only about language. It is a general way to
  make many kinds of things comparable.

### Slide 16 - Good Representations Make Tasks Simple

- A good representation moves complexity into the coordinates.
- Then simple operations become powerful:
  - Nearest neighbor search.
  - Clustering.
  - Ranking.
  - Classification.
  - Recommendation.
  - Outlier detection.

Example:

```text
If "refund request" emails are near each other,
a simple nearest-neighbor system can route new refund emails.
```

Thesis:

> The representation does the hard work. The algorithm often just reads the
> geometry.

### Slide 17 - What Can Go Wrong?

- The representation may preserve the wrong differences.
- It may erase minority patterns.
- It may confuse correlation with meaning.
- It may encode historical bias.
- It may become stale as users or products change.

Examples:

- Users who buy baby products once are represented as "parents" forever.
- A word embedding learns stereotypes from text.
- A recommendation model over-optimizes for clicks and loses user trust.

Key question:

> What does this representation make easy to see, and what does it make hard
> to see?

### Slide 18 - Section 01 Recap

- A representation is a useful encoding, not reality.
- Representations can be hand-designed or learned.
- Vectors make similarity computable.
- Words, users, products, and documents can all be represented.
- The right representation depends on the question.

Transition:

- Now that we have vectors, we need to define "near."

---

## Section 02 - Similarity: Turning Representations Into Questions

### Slide 19 - What Does "Near" Mean?

- Distance: small difference between coordinates.
- Similarity: high alignment between vectors.
- Common choices:
  - Euclidean distance.
  - Cosine similarity.
  - Dot product.
  - Learned scoring function.

Speaker note: introduce only the intuition unless the class needs formulas.

### Slide 20 - Cosine Similarity Intuition

- Cosine asks whether two vectors point in the same direction.
- Useful when magnitude is less important than pattern.
- Common in text and embedding search.

Visual: two arrows from origin, with angle highlighted.

### Slide 21 - Nearest Neighbors

- Given one thing, find the closest things.
- Works for:
  - Similar words.
  - Similar documents.
  - Similar products.
  - Similar users.
  - Similar support tickets.

Demo idea:

- Type a product or phrase.
- Show top 5 nearest neighbors.
- Ask whether the neighbors match the intended meaning.

### Slide 22 - Clustering

- Group things that are close together.
- Useful for discovery:
  - Customer segments.
  - Product families.
  - Topic clusters.
  - Failure modes in support tickets.

Important distinction:

- Clusters are not explanations.
- Clusters are prompts for investigation.

### Slide 23 - Outliers

- If most things live in dense regions, unusual things are far away.
- Outliers can mean:
  - Fraud.
  - Novel demand.
  - Data error.
  - A new market segment.

Question:

- When should an outlier be blocked, reviewed, or celebrated?

---

## Section 03 - Learning Representations From Behavior

### Slide 24 - From Features To Embeddings

- Hand-designed features: humans choose columns.
- Learned embeddings: the system learns coordinates from data.
- The learning objective shapes what the representation captures.

Examples:

- Predict nearby words.
- Predict clicked products.
- Predict watched videos.
- Predict which documents answer the same query.

### Slide 25 - Behavior As Supervision

- Users generate training data by acting.
- Search queries, clicks, purchases, skips, likes, returns, dwell time.
- These signals are noisy but abundant.

Caveat:

- Behavior reveals product interaction, not pure preference.
- Interface design shapes the data.

### Slide 26 - Co-Occurrence

- Things that appear together can be represented as related.
- Examples:
  - Words in the same sentence.
  - Products in the same basket.
  - Songs in the same playlist.
  - Pages in the same session.

Teaching beat:

- Co-occurrence is powerful, but it does not always mean similarity. Socks and
  shoes co-occur because they complement each other, not because they are the
  same kind of product.

### Slide 27 - Latent Factors

- A latent factor is a hidden dimension inferred from patterns.
- In recommender systems:
  - One factor might roughly mean "budget vs premium."
  - Another might mean "sporty vs formal."
  - Another might mean "beginner vs expert."

Important:

- The model does not name the dimensions.
- Humans name them after inspecting patterns.

---

## Section 04 - Recommendations As Geometry

### Slide 28 - The Recommendation Question

- Given a user representation and item representations, rank items.
- Score can be based on:
  - Similarity between user and item vectors.
  - Similarity to recently viewed items.
  - Similarity to users with related behavior.
  - A learned ranking model.

### Slide 29 - Content-Based Recommendation

- Recommend items similar to what the user liked before.
- Uses item features or item embeddings.
- Strengths:
  - Works with fewer users.
  - Easier to explain.
- Weaknesses:
  - Can become narrow.
  - Harder to discover surprising items.

### Slide 30 - Collaborative Filtering

- Recommend based on patterns across users.
- "People who liked this also liked that."
- Uses interaction data.
- Strengths:
  - Captures taste beyond metadata.
  - Finds non-obvious relationships.
- Weaknesses:
  - Cold start for new users/items.
  - Popularity bias.
  - Feedback loops.

### Slide 31 - Hybrid Systems

- Real systems combine representations:
  - Text embeddings.
  - Image embeddings.
  - Metadata.
  - Behavior.
  - Business rules.
  - Safety and diversity constraints.

Thesis:

> Recommendation is not one algorithm. It is a stack of representations,
> scoring rules, constraints, and product choices.

### Slide 32 - Evaluation Questions

- Did users click?
- Did users buy?
- Did users come back?
- Did recommendations improve satisfaction?
- Did the system become too narrow?
- Did some users or products get excluded?

Tie to later course material:

- A better representation is only better if it improves the metric that
  matters, not just the offline similarity score.

---

## Section 05 - Limits, Failure Modes, And Design Choices

### Slide 33 - Representations Are Political And Product Choices

- What you encode affects what the system can see.
- What you omit affects who the system may ignore.
- Historical data can preserve historical unfairness.
- Optimization can amplify the past.

Examples:

- Hiring representations based on previous employees.
- Credit representations based on past lending.
- Music recommendations that over-promote already popular artists.

### Slide 34 - Representation Drift

- Representations can become stale.
- New slang appears.
- Product catalogs change.
- User taste changes.
- New communities enter the system.

Monitoring questions:

- Are nearest neighbors still sensible?
- Are clusters changing?
- Are recommendation outcomes shifting by cohort?
- Are new items stuck with poor representations?

### Slide 35 - The Design Checklist

Before choosing or training a representation, ask:

1. What thing are we representing?
2. What question must this representation help answer?
3. What differences should it preserve?
4. What differences should it ignore?
5. What data creates it?
6. How will we know it is working?
7. Who might it fail for?
8. How will it be updated?

### Slide 36 - Final Takeaways

- Representations make things computable.
- Vectors make similarity, clustering, retrieval, and recommendation possible.
- Similarity is always task-dependent.
- Learned embeddings inherit the incentives and biases of their data.
- Building AI systems means designing representations, not just choosing
  models.

Closing line:

> The model can only reason over the world you represented for it.

---

## Possible Demos

### Demo A - Word Neighbors

- Load a small precomputed word embedding sample.
- Query a word and show nearest neighbors.
- Compare spelling similarity vs semantic similarity.
- Prompt: why is "espresso" near "latte" but not near "express"?

### Demo B - Product Space

- Create a toy product catalog.
- Build three representations:
  - Metadata only.
  - Text description embedding.
  - Purchase co-occurrence.
- Show that the same product has different neighbors in each space.

### Demo C - User/Product Recommendation

- Build a toy matrix of users x products.
- Learn or hand-code 2D latent vectors.
- Show how a user vector scores nearby products.
- Show cold-start failure for a new product.

### Demo D - Representation Failure

- Show a biased or stale representation.
- Example: a user buys one gift and recommendations overfit to that purchase.
- Ask students what signal would repair the representation.

---

## Open Decisions

- Should this be a conceptual lecture only, or include a small coding lab?
- Should the deck use recommender systems as the running example, with words
  as the opening intuition?
- Should embeddings be explained visually first, then mathematically, or keep
  formulas entirely optional?
- What dataset should we use for demos: toy products, movies, songs, or
  course-specific examples?
- How much should this connect to LLM embeddings and vector databases?

