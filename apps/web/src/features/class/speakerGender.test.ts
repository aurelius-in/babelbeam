import { describe, expect, it } from "vitest";
import { genderAriaKey, parseGender } from "./speakerGender";

describe("speaker gender", () => {
  it("maps API values and male/female labels to boy/girl", () => {
    expect(parseGender("boy")).toBe("boy");
    expect(parseGender("male")).toBe("boy");
    expect(parseGender("Female")).toBe("girl");
    expect(parseGender("nope")).toBe("girl");
  });

  it("uses Male/Female aria keys without boy/girl labels", () => {
    expect(genderAriaKey("boy")).toBe("genderMale");
    expect(genderAriaKey("girl")).toBe("genderFemale");
  });
});
