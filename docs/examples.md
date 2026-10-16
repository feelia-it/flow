# Flow examples

## Calculator

```text
Ask for a number and call it first
Ask for another number and call it second
Set result to first + second
Show "The answer is:"
Show result
```

## Organize downloads

```text
In /downloads
If there is a folder containing any of ["Hello", "Accounts", "Payments"]
    If /backup does not exist
        Create folder /backup
    End
    Move it to /backup
End
Show "Organization complete"
```

## Pending CSV report

```text
Read /sales.csv
If there are rows where status is "Pending"
    Save those rows to /reports/pending.csv
    Show "Pending report created"
Otherwise
    Show "No pending orders found"
End
```

