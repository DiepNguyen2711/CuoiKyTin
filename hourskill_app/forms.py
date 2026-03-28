from django import forms

from .models import Course, Video


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ["title", "description", "category_text"]

    def clean_category_text(self):
        category_text = (self.cleaned_data.get("category_text") or "").strip()
        return category_text[:120]


class VideoForm(forms.ModelForm):
    class Meta:
        model = Video
        fields = [
            "title",
            "description",
            "course",
            "category",
            "duration_seconds",
            "is_standalone",
        ]

    def clean_duration_seconds(self):
        duration = self.cleaned_data.get("duration_seconds") or 0
        if duration < 0:
            raise forms.ValidationError("Thời lượng phải lớn hơn hoặc bằng 0.")
        return duration
