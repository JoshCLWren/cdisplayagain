from cdisplayagain import FocusRestorer


def test_focus_restorer_schedules_once_until_run():
    scheduled_callbacks = []
    focused = []

    def fake_after_idle(callback):
        scheduled_callbacks.append(callback)

    def fake_focus():
        focused.append(True)

    restorer = FocusRestorer(fake_after_idle, fake_focus)

    restorer.schedule()
    restorer.schedule()

    assert len(scheduled_callbacks) == 1

    scheduled_callbacks[0]()

    assert focused == [True]

    restorer.schedule()

    assert len(scheduled_callbacks) == 2
