from sqlalchemy import text

_SELECT_COLUMNS = """
    year,
    district,
    total_resident_population,
    total_households,
    gas_supply,
    gas_supply_ratio,
    home_usage,
    public_usage,
    service_usage,
    industry_usage,
    home_ratio,
    public_ratio,
    service_ratio,
    industry_ratio
"""

def get_all_energy_stats(db):
    query = text(f"""
        SELECT {_SELECT_COLUMNS}
        FROM seoul_district_energy_stats
        ORDER BY year, district
    """)
    result = db.execute(query)
    return [dict(row._mapping) for row in result]

def get_energy_stats_by_year(db, year: int):
    query = text(f"""
        SELECT {_SELECT_COLUMNS}
        FROM seoul_district_energy_stats
        WHERE year = :year
        ORDER BY district
    """)
    result = db.execute(query, {"year": year})
    return [dict(row._mapping) for row in result]

def get_energy_stats_by_district(db, district: str):
    query = text(f"""
        SELECT {_SELECT_COLUMNS}
        FROM seoul_district_energy_stats
        WHERE district = :district
        ORDER BY year
    """)
    result = db.execute(query, {"district": district})
    return [dict(row._mapping) for row in result]
