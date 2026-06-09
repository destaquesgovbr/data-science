-- Extract 10k most recent news to JSON
-- Run with: PGPASSWORD=postgres123 psql -h localhost -p 5433 -U postgres -d news_db -f extract_10k_simple.sql > source/rag/data/corpus_10k.json

\pset format unaligned
\pset tuples_only on
\pset fieldsep ''

SELECT jsonb_pretty(
    jsonb_agg(
        jsonb_build_object(
            'id', unique_id,
            'title', COALESCE(title, ''),
            'content', COALESCE(content, ''),
            'metadata', jsonb_build_object(
                'url', COALESCE(url, ''),
                'source_agency', COALESCE(source_agency, ''),
                'category', COALESCE(category, ''),
                'published_at', published_at,
                'updated_at', updated_at,
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
