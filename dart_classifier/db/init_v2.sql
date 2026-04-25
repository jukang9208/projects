CREATE TABLE IF NOT EXISTS dart_corps (
    id            BIGSERIAL PRIMARY KEY,
    corp_code     VARCHAR(8)   NOT NULL UNIQUE,  -- DART 고유 기업코드
    corp_name     VARCHAR(100) NOT NULL,          -- 기업명
    stock_code    VARCHAR(6),                     -- 종목코드 
    modify_date   VARCHAR(8),                     -- DART 최종 수정일 
    created_at    TIMESTAMPTZ DEFAULT NOW()
);


CREATE INDEX IF NOT EXISTS idx_dart_corps_corp_name  ON dart_corps (corp_name);
CREATE INDEX IF NOT EXISTS idx_dart_corps_stock_code ON dart_corps (stock_code);


ALTER TABLE dart_corps ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon read dart_corps" ON dart_corps
    FOR SELECT TO anon USING (true);
CREATE POLICY "service write dart_corps" ON dart_corps
    FOR ALL TO service_role USING (true);