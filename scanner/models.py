from django.db import models
from django.core.exceptions import ValidationError

class TargetSearch(models.Model):
    """Stores the username search request and its tracking state."""

    username = models.CharField(max_length=150, unique=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('running', 'Running'),
            ('completed', 'Completed'),
            ('failed', 'Failed')
        ],
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """
        Enforces choice boundaries programmatically.
        This mirrors the robust testing constraint by preventing invalid status 
        strings from ever polluting your SQLite database rows.
        """
        super().clean()
        valid_statuses = [choice[0] for choice in self._meta.get_field('status').choices]
        if self.status not in valid_statuses:
            raise ValidationError(f"Invalid status state: {self.status}")

    def save(self, *args, **kwargs):
        """
        Forces Django to run clean() validation 
        loops before every database write.
        """

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Target: {self.username} ({self.status})"


class DiscoveredProfile(models.Model):
    """Stores individual public profiles returned by the Maigret engine."""

    target = models.ForeignKey(
        TargetSearch, 
        on_delete=models.CASCADE, 
        related_name='profiles'
    )
    site_name = models.CharField(max_length=100)
    profile_url = models.URLField(max_length=500)
    metadata = models.JSONField(default=dict, blank=True)
    discovered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # Kept perfectly aligned with the 'target' field name mapping
        return f"{self.site_name} - {self.target.username}"
