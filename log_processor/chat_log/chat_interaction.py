from log_processor.chat_log.chat_activity import ChatActivity


class ChatInteraction(ChatActivity):
    """
    Question of user with response of AI
    """

    def __init__(self, messages, users):
        super().__init__(messages, users)

    def check_invariants(self):
        super().check_invariants()

        # Check if the first message is a question
        assert self._messages[0].is_question(), "First message should be a question"

        # Check if the second message is an answer
        assert self._messages[1].is_answer(), "Second message should be an answer"

        # Check if there are only two messages
        assert len(self._messages) == 2, "There should be only two messages"

    def get_waiting_time(self):
        return self._messages[1].time - self._messages[0].time

    def get_summary(self, level=1):
        return (
            f"{'#' * level} Chat interaction\n"
            f"Waiting time: {round(self.get_waiting_time(), 1)}s\n"
            f"{'#' * (level + 1)} Question\n {self._messages[0].body}\n"
            f"{'#' * (level + 1)} Answer\n {self._messages[1].body}"
        )
