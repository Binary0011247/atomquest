from notification_service import run_async
from email_service import (
    send_goal_approved_notification,
    send_goal_returned_notification,
    send_goal_submitted_notification,
)


def notify_goal_submitted(
    manager_email: str,
    manager_name: str,
    employee_name: str,
    goal_count: int,
) -> None:
    run_async(
        send_goal_submitted_notification(
            manager_email, manager_name, employee_name, goal_count
        )
    )


def notify_goal_approved(
    employee_email: str,
    employee_name: str,
    goal_title: str,
    manager_name: str,
) -> None:
    run_async(
        send_goal_approved_notification(
            employee_email, employee_name, goal_title, manager_name
        )
    )


def notify_goal_returned(
    employee_email: str,
    employee_name: str,
    goal_title: str,
    manager_name: str,
    return_reason: str,
) -> None:
    run_async(
        send_goal_returned_notification(
            employee_email, employee_name, goal_title, manager_name, return_reason
        )
    )
