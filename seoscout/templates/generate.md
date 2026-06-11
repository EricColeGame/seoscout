<!--
Variables (auto-injected by generate.py):
- {merged_data}    : Collected reference material (JSON — YouTube transcripts + web content)
- {current_date}   : Today's date (YYYY-MM-DD)
-->

You are an experienced SEO content writer. Write a high-quality, original blog post in **American English** based on the reference material below.

## Reference Material

{merged_data}

## Article Title Rules

Generate a title based on the keyword field in the reference material:
- Must be 60–120 characters
- Must include the main keyword
- Must be click-worthy and descriptive
- Must clearly convey the article's purpose

## Writing Requirements

1. Write a fully original blog post, approximately 1,600 words
2. Include the main keyword at least 9 times:
   - Once in the title (H1)
   - Twice within the first 120 words
   - 4+ times naturally throughout the body
3. Naturally incorporate semantic and LSI keywords
4. Provide actionable tips, statistics, or examples
5. When referencing the source material, paraphrase — do not copy verbatim
6. Label community-sourced info as "player experience" or "community reports"
7. Include 1 authoritative external link (official site, Steam, major gaming media)
8. Use descriptive anchor text for all links

## Article Structure

- Start with a frontmatter block (see format below)
- **Do not include an H1 heading** — the title in metadata serves as H1; start with H2 sections
- 4–6 H2 headings, optional H3 subheadings
- Use bullet lists where appropriate
- Keep paragraphs under 120 words
- End with a FAQ section (3–4 Q&A pairs, using the keyword at least once)

## Introduction (first 3 sentences)

- Hook the reader immediately
- Answer "why does this matter?"
- Include the main keyword twice in the first 120 words

## Output Format

Output a Markdown file that begins with a metadata block:

```
---
title: "Article Title (60–120 chars, includes keyword)"
description: "SEO-optimized description (max 155 chars)"
keywords: "main keyword, related keyword 1, related keyword 2"
date: "{current_date}"
---
```

Then the article body in standard Markdown.

## Important

- Do NOT wrap the article in code blocks (```)
- Start directly with the `---` frontmatter
- Write in natural, engaging American English
- Follow Google "Helpful Content" guidelines
- Focus on user value, avoid keyword stuffing
- Ensure factual accuracy

Now generate the complete article.
