from contextlib import suppress

from django.conf import settings
from django.http import FileResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from ribcage.console import films
from ribcage.console.forms import BackupCodeForm, BackupUploadForm
from ribcage.console.moves import offered
from ribcage.identity.admin_session import admin_required
from ribcage.identity.models import Voter
from ribcage.identity.removal import remove, what_goes
from ribcage.identity.reset import password_digest, reset
from ribcage.operations import offer
from ribcage.operations.backup import describe
from ribcage.phase.history import current, last_entered, move
from ribcage.phase.order import PHASES, MoveRefused, Phase

# Where each phase's work is: Films through VOTE, Pick from PICK on (#28).
WORKING_TABS = {
    Phase.SUGGEST: "console_films",
    Phase.APPROVE: "console_films",
    Phase.VOTE: "console_films",
    Phase.PICK: "console_pick",
    Phase.RUN: "console_pick",
}


def render_tab(request, template, context=None, phase=None):
    # Every tab carries the current phase, as a badge on the Phase tab (#28).
    return render(request, template, {"phase": phase or current(), **(context or {})})


@admin_required
def console(request):
    # Only the landing follows the phase; each tab keeps its own address, so it stays put when the phase moves (#28).
    return redirect(WORKING_TABS[current()])


@admin_required
def phase_tab(request):
    phase = current()
    # Arming is a plain GET that moves nothing; an arm from a tab whose phase is stale arms nothing (#28, #77).
    armed_to = request.GET.get("arm") if request.GET.get("from") == phase else None
    entered = last_entered()
    context = {
        "phases": [(each, entered.get(each)) for each in PHASES],
        "moves": offered(phase, armed_to),
        "voters": Voter.objects.count(),
        "films": films.status(),
    }
    return render_tab(request, "console/phase.html", context, phase)


@admin_required
@require_POST
def move_phase(request):
    # The post names the phase it expects to leave, so a stale tab moves nothing and reloads into the phase as it is (#74, #77).
    with suppress(MoveRefused):
        move(request.POST.get("from_phase"), request.POST.get("to_phase"))
    return redirect("console_phase")


@admin_required
def films_tab(request):
    # A filter is a plain link, so the tab needs no script to read it (the dev, 2026-10-23, on #61).
    ledger = films.ledger(films.chosen(request.GET.get("show")))
    return render_tab(request, "console/films.html", {"ledger": ledger, "screen_time": films.screen_time_words(ledger.screen_time)})


@admin_required
def pick_tab(request):
    return render_tab(request, "console/pick.html")


def named_voter(pk):
    """The voter a form or a link names by id, or None for an id that names nobody, or no id at all (#79)."""
    try:
        return Voter.objects.filter(pk=pk).first()
    except (TypeError, ValueError):
        return None


def render_roster(request, context):
    # The one row open under its voter: an armed act's confirm, or the password a reset just made (#79, #80).
    open_row = context.get("armed") or context.get("was_reset")
    voters = Voter.objects.order_by("display_name_key")
    return render_tab(request, "console/roster.html", {"voters": voters, "tab": "console_roster", "open_row": open_row, **context})


def armed_reset(voter, used=False):
    return {"armed": voter, "arming": "reset", "replacing": password_digest(voter), "used": used}


@admin_required
def roster_tab(request):
    # Arming is a plain GET that changes nothing, naming the voter by id; a row arms one act at a time (#28, #79, #80).
    if armed := named_voter(request.GET.get("remove")):
        return render_roster(request, {"armed": armed, "arming": "remove", "goes": what_goes(armed)})
    if armed := named_voter(request.GET.get("reset")):
        return render_roster(request, armed_reset(armed))
    return render_roster(request, {})


@admin_required
@require_POST
def remove_voter(request):
    # A confirm for a voter already removed, or for nobody, removes nobody and reloads the tab (#79).
    if voter := named_voter(request.POST.get("voter")):
        remove(voter)
    return redirect("console_roster")


@admin_required
@require_http_methods(["GET", "HEAD", "POST"])
@never_cache
def reset_password(request):
    # A GET is a reload onto the page a reset's result was shown at, so it lands on the Roster tab (#76, #80).
    if request.method != "POST":
        return redirect("console_roster")
    # The password is in this response alone, never a redirect's target, so no reload or address can show it again (#80).
    voter = named_voter(request.POST.get("voter"))
    password = voter and reset(voter, request.POST.get("replacing"))
    if password:
        return render_roster(request, {"was_reset": voter, "password": password})
    # Re-read, as the view's copy may predate the reset that refused this confirm, and its digest would be the one just used (#80).
    if voter and (voter := named_voter(voter.pk)):
        # A confirm out of date (a double click, a reload's resubmit) is refused, so say so and offer a fresh one (#80).
        return render_roster(request, armed_reset(voter, used=True))
    return redirect("console_roster")


REFUSALS = {
    offer.NoOffer: "No backup is on offer. Make a code first, in the ribcage container's terminal.",
    offer.Expired: "That code had expired, so the offer is void. Make a new code.",
    offer.WrongCode: "That code is wrong, so the offer is void. Make a new code.",
    offer.WrongPurpose: "That code was made for an upload, so the offer is void. Make a new code with backupcode download.",
}
UPLOAD_REFUSALS = {
    offer.NoOffer: "No code is on offer. Make one first, in the ribcage container's terminal.",
    offer.Expired: "That code had expired, so it is void and the file was not kept. Make a new code.",
    offer.WrongCode: "That code is wrong, so it is void and the file was not kept. Make a new code.",
    offer.WrongPurpose: "That code was made for a download, so it is void and the file was not kept. Make a new code with backupcode upload.",
    offer.TooLarge: f"That file is over {offer.UPLOAD_CAP_MB} MB, far larger than a marathon's backup, so it was not kept. The code wasn't tried, so if it was right it still works.",
    offer.NotADatabase: "That file is not an SQLite database, so it was not kept. The code wasn't tried, so if it was right it still works.",
    offer.FailsIntegrityCheck: "That file failed SQLite's integrity check, so it was not kept. The code wasn't tried, so if it was right it still works.",
}


def render_backup(request, **context):
    # An upload's answer is at the upload's address, so name the tab it belongs to (#86).
    return render_tab(request, "console/backup.html", {"form": BackupCodeForm(), "upload_form": BackupUploadForm(), "tab": "console_backup", **context})


@admin_required
@require_http_methods(["GET", "HEAD", "POST"])
def backup_page(request):
    # A tab, yet only a code from the shell yields the database, never the admin password alone (#54, #68, #86).
    form = BackupCodeForm(request.POST if request.method == "POST" else None)
    if not form.is_valid():
        offer.void_if_expired(settings.BACKUP_OFFER_DIRECTORY, timezone.now())
        return render_backup(request, form=form)
    try:
        redeemed = offer.redeem(settings.BACKUP_OFFER_DIRECTORY, form.cleaned_data["code"], timezone.now(), offer.DOWNLOAD)
    except offer.Refused as refusal:
        return render_backup(request, refusal=REFUSALS[type(refusal)])
    response = FileResponse(offer.opened(redeemed), as_attachment=True, filename=redeemed.file.name, content_type="application/octet-stream")
    response["Cache-Control"] = "no-store"
    return response


def skipped_over_the_cap(request):
    # The upload handler drops a file over the cap, so only the body's length is left to tell it from no file (#81).
    return "backup" not in request.FILES and int(request.META.get("CONTENT_LENGTH") or 0) > offer.UPLOAD_CAP_BYTES


@admin_required
@require_http_methods(["GET", "HEAD", "POST"])
def upload_backup(request):
    # A GET is a reload onto the page an upload's result was shown at, so it lands on the backup page (#76, #81).
    if request.method != "POST":
        return redirect("console_backup")
    # The page only keeps the file, beside the database; the restore is a step in the sidecar's terminal (#81).
    if skipped_over_the_cap(request):
        return refused_upload(request, offer.TooLarge, request.POST.get("code", ""))
    form = BackupUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return render_backup(request, upload_form=form)
    try:
        kept, counts = offer.accept_upload(
            settings.BACKUP_OFFER_DIRECTORY,
            form.cleaned_data["code"],
            form.cleaned_data["backup"].chunks(),
            settings.BACKUP_UPLOAD_DIRECTORY,
            timezone.now(),
        )
    except (offer.Refused, offer.Unkept) as refusal:
        return refused_upload(request, type(refusal), form.cleaned_data["code"])
    return render_backup(request, kept=kept.name, kept_counts=describe(counts), upload_directory=settings.BACKUP_UPLOAD_DIRECTORY)


def refused_upload(request, refusal, code):
    # A file refused for what it is never tries the code, so it stays in the field for the right file (#81).
    still_works = issubclass(refusal, offer.Unkept)
    return render_backup(request, upload_refusal=UPLOAD_REFUSALS[refusal], upload_form=BackupUploadForm(initial={"code": code if still_works else ""}))
