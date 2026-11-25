from automation.scheduler import create_scheduler
from config.settings import SCHEDULER


def test_scheduler_uses_one_serial_pipeline_job():
    scheduler = create_scheduler()

    assert scheduler is not None
    jobs = scheduler.get_jobs()
    assert sorted(job.id for job in jobs) == [
        "hyp3_status_check",
        "phase5_status_export",
        "pipeline_trigger",
        "sentinel1_discovery",
        "stage5_status_export",
    ]
    pipeline_job = scheduler.get_job("pipeline_trigger")
    assert pipeline_job.trigger.interval.total_seconds() == (
        SCHEDULER.monitoring_interval_hours * 60 * 60
    )
    assert pipeline_job.max_instances == 1
