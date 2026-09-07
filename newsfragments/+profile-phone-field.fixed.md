The phone number on the profile edit form can be saved again. It is a split
country-prefix and number widget, and was rendered as a single input whose
name no field ever read, so every save failed as "This field is required".
The two controls now get an outline and label each, side by side, and the
number is optional on this form, as the model has always allowed. `babel`,
which the prefix choices need, is a declared dependency.
