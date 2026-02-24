from domain.events import JobEvaluated, JobQualified


class JobProcessingService:

    def __init__(
        self,
        repository,
        scoring_policy,
        filtering_policy,
        profile,
        event_publisher
    ):
        self.repository = repository
        self.scoring_policy = scoring_policy
        self.filtering_policy = filtering_policy
        self.profile = profile
        self.event_publisher = event_publisher

    def process(self, jobs):

        emitted_events = []

        for job in jobs:

            if self.repository.exists(job.id):
                continue

            if not self.filtering_policy.allows(job, self.profile):
                self.repository.save(job, 0, False)
                continue

            score, _ = self.scoring_policy.evaluate(
                job,
                self.profile
            )

            qualified = self.scoring_policy.qualifies(score)

            self.repository.save(job, score, qualified)

            emitted_events.append(
                JobEvaluated(job.id, score, qualified)
            )

            if qualified:
                emitted_events.append(
                    JobQualified(job.id, score)
                )

        self.event_publisher.publish(emitted_events)