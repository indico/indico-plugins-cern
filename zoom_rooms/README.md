# Zoom Rooms Plugin

## Features

- Synchronizes the calendars of Zoom Rooms-powered devices with the corresponding room occupancy/Zoom meeting

## Changelog

### 3.3

First version

## Details

[**Zoom Rooms**](https://www.zoom.com/en/products/meeting-rooms/) manages its "bookings" through entries in an Exchange calendar. This plugin synchronizes with Exchange a representation of every Indico time slot which fulfils the following criteria:

- Is either a Contribution, Session Block or Event;
- Takes place in a room which has a Zoom Rooms-enabled device (i.e. has a `zoom-rooms-calendar-id` attribute)

![Screenshot of device screen](https://raw.githubusercontent.com/indico/indico-plugins-cern/master/zoom_rooms/assets/logi_screen.png)

This plugin relies on an external custom-built REST API endpoint (not provided) which interfaces on our behalf with the Exchange Graph API.
The logic is very similar to livesync or the exchange sync plugin: a queue of operations is kept in a database table and rolled back in case the request fails.

Objects which are direct tracked by the plugin, through signals, are:

- Events
- Session Blocks
- Contributions
- VC Rooms (associations)

The available operations are:

- CREATE - a new calendar slot should be created, with a given start/end date, location and title
- UPDATE - change the start/end time or title of a calendar slot
- MOVE - change the room ID of a given slot (which practically means deleting it and recreating it in another room's calendar)
- DELETE - delete the slot

This is a summary of the events handled by the plugin and the actions it takes:

| Object         | Change in `{start, end}_dt` | Change in `location`                                                                                      | Change in `block`                   | Create   |
| -------------- | --------------------------- | --------------------------------------------------------------------------------------------------------- | ----------------------------------- | -------- |
| `Event`        | `UPDATE {start_dt, end_dt}` | `CREATE/MOVE/DELETE` depending on the original/target room; trigger change in objects inheriting location | Check change in location for object | `CREATE` |
| `SessionBlock` | `UPDATE {start_dt, end_dt}` | `CREATE/MOVE/DELETE` depending on the original/target room; trigger change in objects inheriting location | Check change in location for object | `CREATE` |
| `Contribution` | `UPDATE {start_dt, end_dt}` | `CREATE/MOVE/DELETE` depending on the original/target room                                                | Check change in location for object | `CREATE` |

| Object                   | Change in name                                  | Create               | Detach               | Attach               | Clone                |
| ------------------------ | ----------------------------------------------- | -------------------- | -------------------- | -------------------- | -------------------- |
| `VCRoom`                 | `UPDATE title` in all `VCRoomEventAssociations` | `CREATE link_object` | N/A | N/A | N/A |
| `VCRoomEventAssociation` | N/A                                             | N/A | `DELETE link_object` | `CREATE link_object` | `CREATE link_object` |

This plugins relies on the `vc_zoom` plugin being available and enabled.
