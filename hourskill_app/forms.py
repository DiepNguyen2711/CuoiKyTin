from django import forms

from .models import Course, Video


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ["title", "description", "category", "bundle_price_tc"]

    def clean_bundle_price_tc(self):
        price = self.cleaned_data.get("bundle_price_tc")
        if price is None:
            return price
        if price < 0:
            raise forms.ValidationError("Giá không được âm.")
        return price


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
