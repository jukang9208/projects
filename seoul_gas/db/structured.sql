-- =====================================================================
-- structured.sql
-- seoul_gas 프로젝트 구조화 데이터 스키마
-- gas_supply / pop_stats / income_stats 테이블 정의
-- =====================================================================

-- gas_supply
CREATE TABLE IF NOT EXISTS public.gas_supply (
    id bigserial PRIMARY KEY,
    district text NOT NULL,
    year int NOT NULL,
    gas_supply int NOT NULL,
    created_at timestamp DEFAULT now(),
    CONSTRAINT unique_gas_supply UNIQUE (district, year)
);

CREATE INDEX IF NOT EXISTS idx_gas_supply_district ON public.gas_supply (district);
CREATE INDEX IF NOT EXISTS idx_gas_supply_year ON public.gas_supply (year);

-- pop_stats
CREATE TABLE IF NOT EXISTS public.pop_stats (
    id bigserial PRIMARY KEY,
    district text NOT NULL,
    year int NOT NULL,
    total_pop int NOT NULL,
    total_households int NOT NULL,
    created_at timestamp DEFAULT now(),
    CONSTRAINT unique_pop_stats UNIQUE (district, year)
);

CREATE INDEX IF NOT EXISTS idx_pop_stats_district ON public.pop_stats (district);
CREATE INDEX IF NOT EXISTS idx_pop_stats_year ON public.pop_stats (year);

-- income_stats
CREATE TABLE IF NOT EXISTS public.income_stats (
    id bigserial PRIMARY KEY,
    district text NOT NULL,
    year int NOT NULL,
    avg_income numeric NOT NULL,
    created_at timestamp DEFAULT now(),
    CONSTRAINT unique_income_stats UNIQUE (district, year)
);

CREATE INDEX IF NOT EXISTS idx_income_stats_district ON public.income_stats (district);
CREATE INDEX IF NOT EXISTS idx_income_stats_year ON public.income_stats (year);

-- RLS 설정
ALTER TABLE public.gas_supply ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pop_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.income_stats ENABLE ROW LEVEL SECURITY;

-- SELECT 허용
DROP POLICY IF EXISTS "Allow read gas_supply" ON public.gas_supply;
CREATE POLICY "Allow read gas_supply"
ON public.gas_supply FOR SELECT USING (true);

DROP POLICY IF EXISTS "Allow read pop_stats" ON public.pop_stats;
CREATE POLICY "Allow read pop_stats"
ON public.pop_stats FOR SELECT USING (true);

DROP POLICY IF EXISTS "Allow read income_stats" ON public.income_stats;
CREATE POLICY "Allow read income_stats"
ON public.income_stats FOR SELECT USING (true);

-- INSERT 허용
DROP POLICY IF EXISTS "Allow insert gas_supply" ON public.gas_supply;
CREATE POLICY "Allow insert gas_supply"
ON public.gas_supply FOR INSERT WITH CHECK (true);

DROP POLICY IF EXISTS "Allow insert pop_stats" ON public.pop_stats;
CREATE POLICY "Allow insert pop_stats"
ON public.pop_stats FOR INSERT WITH CHECK (true);

DROP POLICY IF EXISTS "Allow insert income_stats" ON public.income_stats;
CREATE POLICY "Allow insert income_stats"
ON public.income_stats FOR INSERT WITH CHECK (true);
