from pathlib import Path

import markdown
from django.contrib.auth.decorators import login_not_required
from django.shortcuts import render
from django.utils.safestring import mark_safe

# Inside the package so the image ships it (#49, #51).
# Markdown so the repo copy reads well while the app is down (#16).
POLICY_FILE = Path(__file__).with_name("privacy.md")


@login_not_required
def privacy_policy(request):
    # The file is ours and in the public repo, so its HTML is trusted as written (#49).
    policy = mark_safe(markdown.markdown(POLICY_FILE.read_text(encoding="utf-8")))
    return render(request, "privacy.html", {"policy": policy})
