-- =====================================================================
-- structured.sql
-- seoul_energy 프로젝트 구조화 데이터 스키마
-- 자치구별 가스 수급, 인구, 전력 사용량 등 정형 테이블 정의
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- seoul_gas_supply
-- 가스 수급가구수
CREATE TABLE IF NOT EXISTS public.seoul_gas_supply (
    id bigserial PRIMARY KEY,
    district text NOT NULL,
    year int NOT NULL,
    gas_supply int NOT NULL,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    CONSTRAINT unique_seoul_gas_supply UNIQUE (district, year)
);

CREATE INDEX IF NOT EXISTS idx_seoul_gas_supply_district
    ON public.seoul_gas_supply (district);

CREATE INDEX IF NOT EXISTS idx_seoul_gas_supply_year
    ON public.seoul_gas_supply (year);

-- seoul_pop_stats
-- 총상주인구, 총가구수
CREATE TABLE IF NOT EXISTS public.seoul_pop_stats (
    id bigserial PRIMARY KEY,
    district text NOT NULL,
    year int NOT NULL,
    total_resident_population int NOT NULL,
    total_households int NOT NULL,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    CONSTRAINT unique_seoul_pop_stats UNIQUE (district, year)
);

CREATE INDEX IF NOT EXISTS idx_seoul_pop_stats_district
    ON public.seoul_pop_stats (district);

CREATE INDEX IF NOT EXISTS idx_seoul_pop_stats_year
    ON public.seoul_pop_stats (year);

-- seoul_resident_register_stats
-- 주민등록인구 + 남녀 비율
CREATE TABLE IF NOT EXISTS public.seoul_resident_register_stats (
    id bigserial PRIMARY KEY,
    district text NOT NULL,
    year int NOT NULL,
    total_registered_population int NOT NULL,
    male_population int NOT NULL,
    female_population int NOT NULL,
    male_female_ratio numeric(12,6),
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    CONSTRAINT unique_seoul_resident_register_stats UNIQUE (district, year)
);

CREATE INDEX IF NOT EXISTS idx_seoul_resident_register_stats_district
    ON public.seoul_resident_register_stats (district);

CREATE INDEX IF NOT EXISTS idx_seoul_resident_register_stats_year
    ON public.seoul_resident_register_stats (year);

-- seoul_electricity_usage
-- 가정용소계, 공공용소계, 서비스업소계, 산업용소계
CREATE TABLE IF NOT EXISTS public.seoul_electricity_usage (
    id bigserial PRIMARY KEY,
    district text NOT NULL,
    year int NOT NULL,
    home_usage bigint NOT NULL,
    public_usage bigint NOT NULL,
    service_usage bigint NOT NULL,
    industry_usage bigint NOT NULL,
    total_usage bigint GENERATED ALWAYS AS (
        home_usage + public_usage + service_usage + industry_usage
    ) STORED,
    home_ratio numeric(12,6),
    public_ratio numeric(12,6),
    service_ratio numeric(12,6),
    industry_ratio numeric(12,6),
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    CONSTRAINT unique_seoul_electricity_usage UNIQUE (district, year)
);

CREATE INDEX IF NOT EXISTS idx_seoul_electricity_usage_district
    ON public.seoul_electricity_usage (district);

CREATE INDEX IF NOT EXISTS idx_seoul_electricity_usage_year
    ON public.seoul_electricity_usage (year);

-- seoul_district_energy_stats
-- FastAPI 조회용 최종 통합 테이블
CREATE TABLE IF NOT EXISTS public.seoul_district_energy_stats (
    id bigserial PRIMARY KEY,
    district text NOT NULL,
    year int NOT NULL,

    total_resident_population int NOT NULL,
    total_households int NOT NULL,

    gas_supply int NOT NULL,
    gas_supply_ratio numeric(12,6),

    total_registered_population int,
    male_population int,
    female_population int,
    male_female_ratio numeric(12,6),

    home_usage bigint NOT NULL,
    public_usage bigint NOT NULL,
    service_usage bigint NOT NULL,
    industry_usage bigint NOT NULL,
    total_usage bigint GENERATED ALWAYS AS (
        home_usage + public_usage + service_usage + industry_usage
    ) STORED,

    home_ratio numeric(12,6),
    public_ratio numeric(12,6),
    service_ratio numeric(12,6),
    industry_ratio numeric(12,6),

    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),

    CONSTRAINT unique_seoul_district_energy_stats UNIQUE (district, year)
);

CREATE INDEX IF NOT EXISTS idx_seoul_district_energy_stats_district
    ON public.seoul_district_energy_stats (district);

CREATE INDEX IF NOT EXISTS idx_seoul_district_energy_stats_year
    ON public.seoul_district_energy_stats (year);

-- updated_at function
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- triggers
DROP TRIGGER IF EXISTS trg_set_updated_at_seoul_gas_supply
    ON public.seoul_gas_supply;
CREATE TRIGGER trg_set_updated_at_seoul_gas_supply
BEFORE UPDATE ON public.seoul_gas_supply
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

DROP TRIGGER IF EXISTS trg_set_updated_at_seoul_pop_stats
    ON public.seoul_pop_stats;
CREATE TRIGGER trg_set_updated_at_seoul_pop_stats
BEFORE UPDATE ON public.seoul_pop_stats
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

DROP TRIGGER IF EXISTS trg_set_updated_at_seoul_resident_register_stats
    ON public.seoul_resident_register_stats;
CREATE TRIGGER trg_set_updated_at_seoul_resident_register_stats
BEFORE UPDATE ON public.seoul_resident_register_stats
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

DROP TRIGGER IF EXISTS trg_set_updated_at_seoul_electricity_usage
    ON public.seoul_electricity_usage;
CREATE TRIGGER trg_set_updated_at_seoul_electricity_usage
BEFORE UPDATE ON public.seoul_electricity_usage
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

DROP TRIGGER IF EXISTS trg_set_updated_at_seoul_district_energy_stats
    ON public.seoul_district_energy_stats;
CREATE TRIGGER trg_set_updated_at_seoul_district_energy_stats
BEFORE UPDATE ON public.seoul_district_energy_stats
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

-- RLS enable
ALTER TABLE public.seoul_gas_supply ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.seoul_pop_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.seoul_resident_register_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.seoul_electricity_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.seoul_district_energy_stats ENABLE ROW LEVEL SECURITY;

-- SELECT policies
DROP POLICY IF EXISTS "Allow read seoul_gas_supply"
    ON public.seoul_gas_supply;
CREATE POLICY "Allow read seoul_gas_supply"
ON public.seoul_gas_supply
FOR SELECT
USING (true);

DROP POLICY IF EXISTS "Allow read seoul_pop_stats"
    ON public.seoul_pop_stats;
CREATE POLICY "Allow read seoul_pop_stats"
ON public.seoul_pop_stats
FOR SELECT
USING (true);

DROP POLICY IF EXISTS "Allow read seoul_resident_register_stats"
    ON public.seoul_resident_register_stats;
CREATE POLICY "Allow read seoul_resident_register_stats"
ON public.seoul_resident_register_stats
FOR SELECT
USING (true);

DROP POLICY IF EXISTS "Allow read seoul_electricity_usage"
    ON public.seoul_electricity_usage;
CREATE POLICY "Allow read seoul_electricity_usage"
ON public.seoul_electricity_usage
FOR SELECT
USING (true);

DROP POLICY IF EXISTS "Allow read seoul_district_energy_stats"
    ON public.seoul_district_energy_stats;
CREATE POLICY "Allow read seoul_district_energy_stats"
ON public.seoul_district_energy_stats
FOR SELECT
USING (true);

-- INSERT policies
DROP POLICY IF EXISTS "Allow insert seoul_gas_supply"
    ON public.seoul_gas_supply;
CREATE POLICY "Allow insert seoul_gas_supply"
ON public.seoul_gas_supply
FOR INSERT
WITH CHECK (true);

DROP POLICY IF EXISTS "Allow insert seoul_pop_stats"
    ON public.seoul_pop_stats;
CREATE POLICY "Allow insert seoul_pop_stats"
ON public.seoul_pop_stats
FOR INSERT
WITH CHECK (true);

DROP POLICY IF EXISTS "Allow insert seoul_resident_register_stats"
    ON public.seoul_resident_register_stats;
CREATE POLICY "Allow insert seoul_resident_register_stats"
ON public.seoul_resident_register_stats
FOR INSERT
WITH CHECK (true);

DROP POLICY IF EXISTS "Allow insert seoul_electricity_usage"
    ON public.seoul_electricity_usage;
CREATE POLICY "Allow insert seoul_electricity_usage"
ON public.seoul_electricity_usage
FOR INSERT
WITH CHECK (true);

DROP POLICY IF EXISTS "Allow insert seoul_district_energy_stats"
    ON public.seoul_district_energy_stats;
CREATE POLICY "Allow insert seoul_district_energy_stats"
ON public.seoul_district_energy_stats
FOR INSERT
WITH CHECK (true);

-- UPDATE policies
DROP POLICY IF EXISTS "Allow update seoul_gas_supply"
    ON public.seoul_gas_supply;
CREATE POLICY "Allow update seoul_gas_supply"
ON public.seoul_gas_supply
FOR UPDATE
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS "Allow update seoul_pop_stats"
    ON public.seoul_pop_stats;
CREATE POLICY "Allow update seoul_pop_stats"
ON public.seoul_pop_stats
FOR UPDATE
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS "Allow update seoul_resident_register_stats"
    ON public.seoul_resident_register_stats;
CREATE POLICY "Allow update seoul_resident_register_stats"
ON public.seoul_resident_register_stats
FOR UPDATE
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS "Allow update seoul_electricity_usage"
    ON public.seoul_electricity_usage;
CREATE POLICY "Allow update seoul_electricity_usage"
ON public.seoul_electricity_usage
FOR UPDATE
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS "Allow update seoul_district_energy_stats"
    ON public.seoul_district_energy_stats;
CREATE POLICY "Allow update seoul_district_energy_stats"
ON public.seoul_district_energy_stats
FOR UPDATE
USING (true)
WITH CHECK (true);
