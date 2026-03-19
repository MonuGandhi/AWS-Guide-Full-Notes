# Day‑4 — IAM Policy Language Basics (Hinglish)

## ✅ Objective
- IAM policy language ke basics समझना  
- 2 tiny policies लिखना (S3 read‑only + dangerous action deny)  
- Notes repo में save करना  

---

## 1) IAM Policy ka basic structure
IAM policy एक JSON document होता है. Structure:

- **Version**  
- **Statement** (array of statements)

Statement में main rules आते हैं. Order matter नहीं करता.

--

## 2) Core Policy Elements

### ✅ Version  
Policy language version बताता है. AWS recommend करता है:
```
"Version": "2012-10-17"
```

### ✅ Statement  
Multiple permission rules लिख सकते हो.

### ✅ Effect  
Allow / Deny  
> Explicit Deny हमेशा Allow को override करता है.

### ✅ Action  
कौन‑सा API call allow/deny करना है.  
Format: `service:Action`  
Example: `s3:GetObject`

### ✅ Resource  
किस resource पर action apply होगा.  
S3 ARN examples:
- Bucket: `arn:aws:s3:::bucket-name`
- Objects: `arn:aws:s3:::bucket-name/*`

### ✅ Condition (optional)  
Extra filters जैसे IP, MFA, time, region आदि.

---

## 3) Policy Evaluation (Important)
- Default = **Deny**
- Allow मिलने पर access मिल सकता है
- **Explicit Deny** मिले तो request block

---

# ✅ Tiny Policy #1 — S3 Read‑Only
> Replace **my-bucket-name** अपने bucket नाम से.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3ReadOnlyBucket",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetObject"
      ],
      "Resource": [
        "arn:aws:s3:::my-bucket-name",
        "arn:aws:s3:::my-bucket-name/*"
      ]
    }
  ]
}
```

---

# ✅ Tiny Policy #2 — Dangerous Action Deny
Example: S3 bucket delete deny करना

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyS3BucketDelete",
      "Effect": "Deny",
      "Action": "s3:DeleteBucket",
      "Resource": "*"
    }
  ]
}
```

---

## ✅ Day‑4 Complete
- Policy elements समझे  
- 2 policies लिखीं  
- Notes repo में ready  
