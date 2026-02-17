import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ingestion.scrapers.europa_league_scraper import run as scrape_europa_league
from ingestion.scrapers.european_leagues_scraper import run as scrape_european_leagues
from processing.data_cleaning import process_and_save


def main():
    parser = argparse.ArgumentParser(
        description="Fair Play Shield - Sistema de detección de partidos amañados"
    )
    parser.add_argument(
        "--step",
        choices=["scrape", "process", "all"],
        default="all",
        help="Paso a ejecutar: scrape, process, all",
    )
    parser.add_argument(
        "--seasons",
        type=int,
        default=5,
        help="Número de temporadas hacia atrás (default: 5)",
    )
    args = parser.parse_args()

    if args.step in ("scrape", "all"):
        print("\n" + "=" * 60)
        print("PASO 1A: DESCARGA UEFA EUROPA LEAGUE")
        print("=" * 60)
        df_el, el_path = scrape_europa_league(seasons_back=args.seasons)
        if df_el is not None:
            print(f"[OK] Europa League: {len(df_el)} partidos")
        else:
            print("[WARN] No se pudieron obtener datos de Europa League")

        print("\n" + "=" * 60)
        print("PASO 1B: DESCARGA LIGAS EUROPEAS (con cuotas)")
        print("=" * 60)
        df_leagues, leagues_path = scrape_european_leagues(seasons_back=args.seasons)
        if df_leagues is not None:
            print(f"[OK] Ligas europeas: {len(df_leagues)} partidos")
        else:
            print("[WARN] No se pudieron obtener datos de ligas europeas")

        if df_el is None and df_leagues is None:
            print("[FATAL] No se pudieron obtener datos de ninguna fuente. Abortando.")
            sys.exit(1)

    if args.step in ("process", "all"):
        print("\n" + "=" * 60)
        print("PASO 2: LIMPIEZA Y FEATURE ENGINEERING")
        print("=" * 60)

        input_files = []
        raw_dir = Path(__file__).resolve().parent / "data" / "raw"
        for f in ["europa_league_matches.csv", "european_leagues_with_odds.csv"]:
            if (raw_dir / f).exists():
                input_files.append(f)

        if not input_files:
            print("[FATAL] No hay archivos de datos para procesar.")
            sys.exit(1)

        for input_file in input_files:
            output_file = input_file.replace(".csv", "_processed.csv")
            print(f"\n  Procesando: {input_file}")
            try:
                df_processed, proc_path = process_and_save(input_file, output_file)
                print(f"  [OK] {len(df_processed)} partidos procesados → {output_file}")

                if "total_flags" in df_processed.columns:
                    suspicious = df_processed[df_processed["total_flags"] >= 2].sort_values(
                        "total_flags", ascending=False
                    )
                    if not suspicious.empty:
                        display_cols = ["date", "home_team", "away_team", "home_goals",
                                        "away_goals", "result", "season", "total_flags"]
                        available = [c for c in display_cols if c in suspicious.columns]
                        print(f"\n  Partidos con 2+ anomalías ({len(suspicious)}):")
                        print(f"  {suspicious[available].head(15).to_string(index=False)}")
            except Exception as e:
                print(f"  [ERROR] {e}")

    print("\n" + "=" * 60)
    print("FAIR PLAY SHIELD - Pipeline completado!")
    print("=" * 60)
    print("\nArchivos generados en data/:")
    data_dir = Path(__file__).resolve().parent / "data"
    for subdir in ["raw", "processed"]:
        d = data_dir / subdir
        if d.exists():
            for f in sorted(d.glob("*.csv")):
                size_mb = f.stat().st_size / (1024 * 1024)
                print(f"  {subdir}/{f.name} ({size_mb:.1f} MB)")

    print("\nPróximos pasos:")
    print("  1. Revisar datos en data/processed/")
    print("  2. Ejecutar notebooks de análisis exploratorio")
    print("  3. Entrenar modelos de detección de anomalías")


if __name__ == "__main__":
    main()
