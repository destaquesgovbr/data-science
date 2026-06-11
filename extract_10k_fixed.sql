-- Extract 10k with correct structure for index_corpus.py
\pset format unaligned
\pset tuples_only on
\pset fieldsep ''

SELECT jsonb_pretty(
    jsonb_agg(
        jsonb_build_object(
            'id', unique_id,
            'title', COALESCE(title, ''),
            'content', COALESCE(content, ''),
            'url', COALESCE(url, ''),
            'source_agency', COALESCE(source_agency, ''),
            'category', COALESCE(category, ''),
            'published_at', published_at,
            'updated_at', updated_at,
            'metadata', jsonb_build_object(
                'subtitle', COALESCE(subtitle, ''),
                'editorial_lead', COALESCE(editorial_lead, ''),
                'summary', COALESCE(summary, ''),
                'tags', COALESCE(tags, ARRAY[]::text[]),
                'original_metadata', COALESCE(metadata, '{}'::jsonb)
            )
        )
    )
)
FROM (
    SELECT *
    FROM news_corpus_repository
    ORDER BY published_at DESC NULLS LAST
    LIMIT 10000
) subq;
