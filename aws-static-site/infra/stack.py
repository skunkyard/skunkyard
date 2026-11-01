"""A static site on AWS: S3 and CloudFront static site with its certificate and DNS records.

GitHub Actions runs this program on every push to main. The hosted zone, the Pulumi
state bucket, and the GitHub role come from `bootstrap.yaml`, run once by hand.
"""

import json

import pulumi
import pulumi_aws as aws

DOMAIN = pulumi.Config().require("domain")
WWW = f"www.{DOMAIN}"

# AWS managed policies: CachingOptimized and SecurityHeadersPolicy.
CACHING_OPTIMIZED = "658327ea-f89d-4fab-a63d-7e88639e58f6"
SECURITY_HEADERS = "67f7725c-6f97-4210-82d7-5512b31e9d03"

# ── DNS and certificate ──────────────────────────────────────────────────────
zone = aws.route53.get_zone(name=DOMAIN)

cert = aws.acm.Certificate(
    "cert", domain_name=DOMAIN, subject_alternative_names=[WWW], validation_method="DNS"
)
validation_records = [
    aws.route53.Record(
        f"cert-validation-{i}",
        zone_id=zone.zone_id,
        name=cert.domain_validation_options[i].resource_record_name,
        type=cert.domain_validation_options[i].resource_record_type,
        records=[cert.domain_validation_options[i].resource_record_value],
        ttl=300,
        allow_overwrite=True,
    )
    for i in range(2)
]
validated = aws.acm.CertificateValidation(
    "cert",
    certificate_arn=cert.arn,
    validation_record_fqdns=[r.fqdn for r in validation_records],
)

# ── Bucket ───────────────────────────────────────────────────────────────────
# The GitHub role may only touch buckets named my-site-*.
bucket = aws.s3.Bucket("site", bucket_prefix="my-site-files-")
aws.s3.BucketPublicAccessBlock(
    "site",
    bucket=bucket.id,
    block_public_acls=True,
    block_public_policy=True,
    ignore_public_acls=True,
    restrict_public_buckets=True,
)
aws.s3.BucketVersioning("site", bucket=bucket.id, versioning_configuration={"status": "Enabled"})
aws.s3.BucketLifecycleConfiguration(
    "site",
    bucket=bucket.id,
    rules=[
        {
            "id": "expire-old-versions",
            "status": "Enabled",
            "filter": {},
            "noncurrent_version_expiration": {"noncurrent_days": 30},
        }
    ],
)

# ── CloudFront ───────────────────────────────────────────────────────────────
# Redirects www to the apex, and maps /about/ and /about to /about/index.html.
router = aws.cloudfront.Function(
    "router",
    runtime="cloudfront-js-2.0",
    publish=True,
    code=f"""function handler(event) {{
  var request = event.request;
  var host = request.headers.host ? request.headers.host.value : '';
  if (host === '{WWW}') {{
    return {{
      statusCode: 301,
      statusDescription: 'Moved Permanently',
      headers: {{ location: {{ value: 'https://{DOMAIN}' + request.uri }} }}
    }};
  }}
  if (request.uri.endsWith('/')) {{
    request.uri += 'index.html';
  }} else if (!request.uri.split('/').pop().includes('.')) {{
    request.uri += '/index.html';
  }}
  return request;
}}
""",
)

oac = aws.cloudfront.OriginAccessControl(
    "site",
    origin_access_control_origin_type="s3",
    signing_behavior="always",
    signing_protocol="sigv4",
)

distribution = aws.cloudfront.Distribution(
    "site",
    enabled=True,
    is_ipv6_enabled=True,
    http_version="http2and3",
    price_class="PriceClass_100",
    aliases=[DOMAIN, WWW],
    default_root_object="index.html",
    origins=[
        {
            "origin_id": "s3",
            "domain_name": bucket.bucket_regional_domain_name,
            "origin_access_control_id": oac.id,
        }
    ],
    default_cache_behavior={
        "target_origin_id": "s3",
        "viewer_protocol_policy": "redirect-to-https",
        "allowed_methods": ["GET", "HEAD"],
        "cached_methods": ["GET", "HEAD"],
        "compress": True,
        "cache_policy_id": CACHING_OPTIMIZED,
        "response_headers_policy_id": SECURITY_HEADERS,
        "function_associations": [{"event_type": "viewer-request", "function_arn": router.arn}],
    },
    # S3 answers 403 for a missing file through OAC. Both codes must become a real
    # 404; answering 200 makes soft 404s that search engines index.
    custom_error_responses=[
        {
            "error_code": code,
            "response_code": 404,
            "response_page_path": "/404.html",
            "error_caching_min_ttl": 0,
        }
        for code in (403, 404)
    ],
    restrictions={"geo_restriction": {"restriction_type": "none"}},
    viewer_certificate={
        "acm_certificate_arn": validated.certificate_arn,
        "ssl_support_method": "sni-only",
        "minimum_protocol_version": "TLSv1.2_2021",
    },
)

bucket_policy = aws.s3.BucketPolicy(
    "site",
    bucket=bucket.id,
    policy=pulumi.Output.all(bucket.arn, distribution.arn).apply(
        lambda arns: json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "cloudfront.amazonaws.com"},
                        "Action": "s3:GetObject",
                        "Resource": f"{arns[0]}/*",
                        "Condition": {"StringEquals": {"AWS:SourceArn": arns[1]}},
                    }
                ],
            }
        )
    ),
)

for host in (DOMAIN, WWW):
    for record_type in ("A", "AAAA"):
        aws.route53.Record(
            f"{host}-{record_type}",
            zone_id=zone.zone_id,
            name=host,
            type=record_type,
            aliases=[
                {
                    "name": distribution.domain_name,
                    "zone_id": distribution.hosted_zone_id,
                    "evaluate_target_health": False,
                }
            ],
        )

# No mail yet: a null MX and an SPF that allows no senders, so nobody can send as the domain.
for record_type, value in (("MX", "0 ."), ("TXT", "v=spf1 -all")):
    aws.route53.Record(
        f"no-mail-{record_type}",
        zone_id=zone.zone_id,
        name=DOMAIN,
        type=record_type,
        ttl=3600,
        records=[value],
    )

pulumi.export("bucket_name", bucket.bucket)
pulumi.export("distribution_id", distribution.id)
