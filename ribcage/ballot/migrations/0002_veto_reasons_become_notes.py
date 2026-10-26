"""A veto's reason becomes the voter's note on the film: a new note where there is none, after a blank line under an existing one (#128)."""

from django.db import migrations


def move_reasons_into_notes(apps, schema_editor):
    BallotRecord = apps.get_model("ballot", "BallotRecord")
    Note = apps.get_model("suggestions", "Note")
    for record in BallotRecord.objects.exclude(veto_reason__isnull=True).exclude(veto_reason=""):
        note = Note.objects.filter(suggestion_id=record.suggestion_id, author_id=record.voter_id).first()
        if note is None:
            Note.objects.create(suggestion_id=record.suggestion_id, author_id=record.voter_id, text=record.veto_reason)
        else:
            note.text = f"{note.text}\n\n{record.veto_reason}"
            note.save(update_fields=["text"])


class Migration(migrations.Migration):

    dependencies = [
        ("ballot", "0001_ballot_records_and_done_markers"),
        ("suggestions", "0001_suggestions_and_notes"),
    ]

    # Going back leaves the restored field empty: the text stays in the notes.
    operations = [migrations.RunPython(move_reasons_into_notes, migrations.RunPython.noop)]
