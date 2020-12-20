from kueue.consumer import TaskExecutorConsumer, TaskMessage


def return_args(*args, **kwargs):
    return args, kwargs


class SingleTaskConsumer(TaskExecutorConsumer):
    def on_success(self, message: TaskMessage, result):
        super().on_success(message, result)
        self.stop()

    def on_error(self, message: TaskMessage):
        super().on_error(message)
        self.stop()
