from automation.scheduler import create_scheduler
from config.settings import SCHEDULER


def test_scheduler_uses_one_serial_pipeline_job():
    scheduler = create_scheduler()

    assert scheduler is not None
    jobs = scheduler.get_jobs()
    assert [job.id for job in jobs] == ["pipeline_trigger"]
    assert jobs[0].trigger.interval.total_seconds() == (
        SCHEDULER.monitoring_interval_hours * 60 * 60
    )
    assert jobs[0].max_instances == 1
