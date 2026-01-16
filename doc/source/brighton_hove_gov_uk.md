# Brighton and Hove City Council

Support for schedules provided by [Brighton and Hove City Council](https://www.brighton-hove.gov.uk/), UK.

## Configuration via configuration.yaml

```yaml
waste_collection_schedule:
    sources:
    - name: brighton_hove_gov_uk
      args:
        postcode: POSTCODE
        uprn: UPRN
```

### Configuration Variables

**postcode**
*(string) (required)*
Postcode of the property

**uprn**
*(integer) (required)*
UPRN (Unique Property Reference Number) of the property

## Example

```yaml
waste_collection_schedule:
    sources:
    - name: brighton_hove_gov_uk
      args:
        postcode: BN1 1AA
        uprn: 000040082756
```

## How to get the UPRN argument

You can find the UPRN for your property using the [UK Land Registry](https://www.gov.uk/guidance/finding-property-information) or by checking the Brighton and Hove City Council website.
