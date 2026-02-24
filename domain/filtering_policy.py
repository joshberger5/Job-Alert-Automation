class FilteringPolicy:

    def allows(self, job, profile) -> bool:
        location_text = job.location.lower()

        if profile.remote_allowed and "remote" in job.description.lower():
            return True

        for location in profile.preferred_locations:
            if location.lower() in location_text:
                return True

        return False