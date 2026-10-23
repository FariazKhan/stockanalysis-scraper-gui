def main():
    import pandas as pd
    import numpy as np
    import os
    
    
    INPUT = "output/portfolio_master.csv"
    OUTPUT = "output/portfolio_ranked.csv"
    
    
    
    def percentile_score(series, higher=True):
    
        """
        Convert values into 0-100 percentile scores
        """
    
        if higher:
            return series.rank(pct=True) * 100
    
        else:
            return (1 - series.rank(pct=True)) * 100
    
    
    
    def mean_available(df, cols):
    
        available = []
    
        for c in cols:
            if c in df.columns:
                available.append(c)
    
        return df[available].mean(axis=1)
    
    
    
    df = pd.read_csv(INPUT)
    
    
    
    # =====================================================
    # QUALITY SCORE
    # =====================================================
    
    quality_cols = [
        "roe",
        "roa",
        "roic",
        "roce",
        "gross_margin",
        "operating_margin",
        "net_margin"
    ]
    
    
    quality_components = []
    
    
    for c in quality_cols:
    
        if c in df.columns:
    
            quality_components.append(
                percentile_score(
                    df[c],
                    higher=True
                )
            )
    
    
    df["quality_score"] = (
        pd.concat(
            quality_components,
            axis=1
        )
        .mean(axis=1)
    )
    
    
    
    # =====================================================
    # VALUE SCORE
    # =====================================================
    
    # Lower valuation is better
    
    value_cols_low = [
        "pe",
        "peForward",
        "pb",
        "ps",
        "evrevenue",
        "evebitda",
        "pfcf"
    ]
    
    
    value_components = []
    
    
    for c in value_cols_low:
    
        if c in df.columns:
    
            value_components.append(
                percentile_score(
                    df[c],
                    higher=False
                )
            )
    
    
    # Dividend yield higher is better
    
    if "dividendyield" in df.columns:
    
        value_components.append(
            percentile_score(
                df["dividendyield"],
                higher=True
            )
        )
    
    
    
    df["value_score"] = (
        pd.concat(
            value_components,
            axis=1
        )
        .mean(axis=1)
    )
    
    
    
    # =====================================================
    # GROWTH SCORE
    # =====================================================
    
    growth_cols = [
        "revenue_cagr",
        "net_income_cagr",
        "eps_cagr"
    ]
    
    
    growth_components=[]
    
    
    for c in growth_cols:
    
        if c in df.columns:
    
            growth_components.append(
                percentile_score(
                    df[c],
                    higher=True
                )
            )
    
    
    df["growth_score"] = (
        pd.concat(
            growth_components,
            axis=1
        )
        .mean(axis=1)
    )
    
    
    
    # =====================================================
    # FINANCIAL HEALTH SCORE
    # =====================================================
    
    
    health_components=[]
    
    
    # Lower debt is better
    
    for c in [
        "debtequity",
        "debtebitda"
    ]:
    
        if c in df.columns:
    
            health_components.append(
                percentile_score(
                    df[c],
                    higher=False
                )
            )
    
    
    # Higher liquidity is better
    
    for c in [
        "currentratio",
        "quickRatio"
    ]:
    
        if c in df.columns:
    
            health_components.append(
                percentile_score(
                    df[c],
                    higher=True
                )
            )
    
    
    
    df["financial_health_score"] = (
        pd.concat(
            health_components,
            axis=1
        )
        .mean(axis=1)
    )
    
    
    
    # =====================================================
    # COMPOSITE SCORE
    # =====================================================
    
    
    df["composite_score"] = (
    
        df["quality_score"] * 0.30 +
    
        df["value_score"] * 0.25 +
    
        df["growth_score"] * 0.25 +
    
        df["financial_health_score"] * 0.20
    
    )
    
    
    df["rank"] = (
        df["composite_score"]
        .rank(
            ascending=False,
            method="dense",
            na_option="bottom"
        )
    )
    
    df["rank"] = df["rank"].fillna(
        len(df)+1
    ).astype(int)
    
    
    
    # Sort
    
    df = df.sort_values(
        "rank"
    )
    
    
    
    # Save
    df = df.fillna(0)
    df.to_csv(
        OUTPUT,
        index=False
    )
    
    
    
    print("="*60)
    print("Portfolio Analysis Completed")
    print("="*60)
    
    print()
    
    print(
        df[
            [
                "rank",
                "ticker",
                "quality_score",
                "value_score",
                "growth_score",
                "financial_health_score",
                "composite_score"
            ]
        ]
        .to_string(index=False)
    )
    
    
    print()
    print("Saved:")
    print(OUTPUT)
if __name__ == '__main__':
    main()
