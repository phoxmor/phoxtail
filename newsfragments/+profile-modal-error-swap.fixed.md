The edit-profile drawer stays open when a save fails. The error response
re-rendered the whole drawer into the modal placeholder, replaying its open
animation; it now swaps only the form out of band.
