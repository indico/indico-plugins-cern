# Burotel

![](https://raw.githubusercontent.com/indico/indico-plugins-cern/master/burotel/docs/burotel_screenshot.png)

**Burotel** is a CERN-specific [Indico](https://getindico.io) plugin which leverages the Room Booking system in order
to allow for the management of desks in open spaces. It is built as a thin layer on top of the original booking system,
with some additional customizations, constraints and integrations.

## Differences with base Indico

 * The unit of booking is the **desk**;
 * All Bookings have **1-day granularity** (00:00 - 23:59) and **daily** recurrence;
 * Desks in the same room have the same `building`, `floor` and `number` codes. Only the `verbose_name` differs;
 * **No user** can have **more than one booking in parallel**;
 * The **reason** field is not customizable (all bookings have `Burotel booking` as a reason);
 * The `division` field is used to filter the rooms **by experiment**;
 * Room suggestions are disabled;


### Long-term desks

![](https://raw.githubusercontent.com/indico/indico-plugins-cern/master/burotel/docs/long_term.png)

**Long-term desks** are rooms which are meant to be used for long-term bookings. They are set using the "Long-term
desk" attribute (`long-term`).

### Integration with ADaMS

Indico will automatically notify ADaMS about bookings in any rooms where the `electronic-lock` attribute set to `yes`.
This will happen on:
 * Booking creation (not pre-bookings)
 * Pre-booking confirmation
 * Booking changes (start date and length of booking)
 * Booking cancellation (or pre-booking rejection)

The synchronization with ADaMS is **immediate**.

### Auto-cancellation of Pre-bookings

Pre-bookings in rooms which have the `confirmation-by-secretariat` attribute set to `yes` will be **automatically
cancelled** unless confirmed within **3 working days** of their beginning. This will normally be done by the user,
in person, at the Experiment/Department secretariat. This features is meant to make it less probably that someone
will request a desk and then forget about it and not use it.

## CLI

The `indico burotel` command can be used to perform a series of maintenance operations:

 * **`export`** - Export desk list to a CSV file.
 * **`geocode`** - Set geographical location for all desks/buildings.
 * **`update`** - Update the Burotels from a CSV file.
