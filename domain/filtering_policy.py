from domain.candidate_profile import CandidateProfile
from domain.job import Job


class FilteringPolicy:

    def allows(self, job: Job, profile: CandidateProfile) -> bool:
        # Filter out contract roles if the candidate isn't open to them
        if not profile.open_to_contract and job.employment_type == "contract":
            return False

        # Remote check: trust the explicit flag when set; fall back to text for None
        if profile.remote_allowed:
            if job.remote is True:
                return True
            if job.remote is None:  # unknown — fall back to text parsing
                if "remote" in job.description.lower() or "remote" in job.location.lower():
                    return True

        # Location check
        location_text = job.location.lower()
        for location in profile.preferred_locations:
            if location.lower() in location_text:
                return True

        return False
