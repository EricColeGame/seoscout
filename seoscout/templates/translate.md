<!--
Variables (auto-injected by translate.py):
- $language_name   : Target language name (e.g. Spanish, Japanese)
- $lang_code       : Target language code (e.g. es, ja)
- $content         : English MDX article content to translate
-->

Translate the following MDX content from English to $language_name.

IMPORTANT RULES:
1. Translate ALL text content naturally and fluently to $language_name
2. Keep ALL Markdown formatting intact (headings ##, lists -, bold **, links [], tables, etc.)
3. Keep ALL HTML tags unchanged
4. Keep ALL URLs unchanged
5. Maintain the same article structure and length

METADATA TRANSLATION RULES:
- title: Must be translated to $language_name
- description: Must be translated to $language_name
- summary: Must be translated to $language_name (if present)
- Keep ALL other metadata fields unchanged (category, date, lastModified, image, etc.)
- The metadata block MUST remain as a JavaScript export, NOT YAML frontmatter

TARGET LANGUAGE: $language_name ($lang_code)

ORIGINAL CONTENT IN ENGLISH:

$content

CRITICAL OUTPUT RULES:
1. Output ONLY the translated MDX content directly
2. Start directly with `export const metadata = {` — do NOT use YAML frontmatter (---)
3. DO NOT wrap the output in code blocks
4. DO NOT add any explanations or commentary
5. The output must be a valid .mdx file with JS export metadata followed by Markdown body
