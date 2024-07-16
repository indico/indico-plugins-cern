# Labotel

**Labotel** is a CERN-specific [Indico](https://getindico.io) plugin which leverages the Room Booking system in order
to allow for the management of lab spaces/equipment. It is built as a thin layer on top of the original booking system,
with some additional customizations, constraints and integrations.

## CLI

The `indico labotel` command can be used to perform a series of maintenance operations:

 * **`export`** - Export desk list to a CSV file.
 * **`geocode`** - Set geographical location for all desks/buildings.
 * **`update`** - Update the Labotels from a CSV file.
