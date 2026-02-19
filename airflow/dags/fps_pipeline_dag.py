from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator
import sys
import os

sys.path.insert(0, '/opt/airflow/project')

default_args = {
    'owner': 'fair_play_shield',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

def task_ingest_european_leagues(**context):
    from ingestion.scrapers.european_leagues_scraper import run as run_european
    seasons_back = context['params'].get('seasons_back', 3)
    run_european(seasons_back=seasons_back)

def task_ingest_europa_league(**context):
    from ingestion.scrapers.europa_league_scraper import run as run_el
    seasons_back = context['params'].get('seasons_back', 3)
    run_el(seasons_back=seasons_back)

def task_process_data(**context):
    from processing.data_cleaning import process_and_save
    for input_file, output_file in [
        ("european_leagues_with_odds.csv", "european_leagues_with_odds_processed.csv"),
        ("europa_league_matches.csv", "europa_league_matches_processed.csv"),
    ]:
        try:
            process_and_save(input_file, output_file)
        except FileNotFoundError:
            pass

def task_train_and_score(**context):
    from models.integrity_scorer import train_and_score
    train_and_score()

def task_notify_completion(**context):
    execution_date = context['execution_date']
    print(f"✅ Pipeline completed successfully at {execution_date}")
    print("📊 Dashboard ready at http://localhost:8050")
    print("📈 MLflow UI at http://localhost:5001")

with DAG(
    'fps_pipeline',
    default_args=default_args,
    description='Fair Play Shield - Match Integrity Pipeline',
    schedule_interval='0 6 * * 1',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['fair_play_shield', 'ml', 'integrity'],
    params={'seasons_back': 3},
) as dag:

    start = EmptyOperator(task_id='start')

    ingest_european = PythonOperator(
        task_id='ingest_european_leagues',
        python_callable=task_ingest_european_leagues,
        provide_context=True,
    )

    ingest_el = PythonOperator(
        task_id='ingest_europa_league',
        python_callable=task_ingest_europa_league,
        provide_context=True,
    )

    process = PythonOperator(
        task_id='process_data',
        python_callable=task_process_data,
        provide_context=True,
    )

    train = PythonOperator(
        task_id='train_and_score',
        python_callable=task_train_and_score,
        provide_context=True,
    )

    notify = PythonOperator(
        task_id='notify_completion',
        python_callable=task_notify_completion,
        provide_context=True,
    )

    end = EmptyOperator(task_id='end')

    start >> [ingest_european, ingest_el] >> process >> train >> notify >> end
