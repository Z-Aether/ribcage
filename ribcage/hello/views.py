from django.contrib.auth.decorators import login_not_required
from django.shortcuts import redirect, render

from ribcage.hello.forms import MessageForm
from ribcage.hello.models import KEPT_MESSAGES, Message


# Public until M3 removes it; the zero-query invariant's test lists it as an exception (#42, #49).
@login_not_required
def hello(request):
    if request.method == "POST":
        form = MessageForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("hello")
    else:
        form = MessageForm()
    # bulk_create and loaddata skip save()'s trimming, so the page caps the rows it lists too (#47).
    latest_messages = Message.newest_first()[:KEPT_MESSAGES]
    return render(request, "hello/hello.html", {"form": form, "latest_messages": latest_messages})
