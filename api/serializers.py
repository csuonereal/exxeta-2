from rest_framework import serializers


class CreateSessionSerializer(serializers.Serializer):
    prompt = serializers.CharField(max_length=20_000)
    provider = serializers.ChoiceField(choices=["openai", "gemini"])
    api_key = serializers.CharField(max_length=500, write_only=True)
    model_name = serializers.CharField(max_length=100, required=False, default=None)
