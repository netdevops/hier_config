use rustc_hash::FxHashSet as HashSet;

/// Upper bound on the number of elements a single `a-b` range segment may expand to.
pub const MAX_RANGE_SPAN: u32 = 1_000_000;

/// Upper bound on the total number of values one range string may expand to.
pub const MAX_RANGE_TOTAL: u64 = 1_000_000;

/// Expands number range strings like "2-5,8,22-45" into a de-duplicated, ordered list.
///
/// # Errors
///
/// Returns a static message if a segment is not a number or an ascending `a-b`
/// range of numbers.
pub fn expand_range(number_range_str: &str) -> Result<Vec<u32>, &'static str> {
    let mut numbers = Vec::new();
    let mut seen = HashSet::default();
    let mut visited: u64 = 0;
    for segment in number_range_str.split(',') {
        let start_stop: Vec<&str> = segment.split('-').collect();
        match start_stop.len() {
            1 => {
                let n: u32 = start_stop[0]
                    .trim()
                    .parse()
                    .map_err(|_| "parse int error")?;
                visited += 1;
                if visited > MAX_RANGE_TOTAL {
                    return Err("range too large");
                }
                if seen.insert(n) {
                    numbers.push(n);
                }
            }
            2 => {
                let start: u32 = start_stop[0]
                    .trim()
                    .parse()
                    .map_err(|_| "parse int error")?;
                let stop: u32 = start_stop[1]
                    .trim()
                    .parse()
                    .map_err(|_| "parse int error")?;
                if stop < start {
                    return Err("reversed range segment");
                }
                if stop - start >= MAX_RANGE_SPAN {
                    return Err("range segment too large");
                }
                visited += u64::from(stop - start) + 1;
                if visited > MAX_RANGE_TOTAL {
                    return Err("range too large");
                }
                for n in start..=stop {
                    if seen.insert(n) {
                        numbers.push(n);
                    }
                }
            }
            _ => return Err("invalid range segment"),
        }
    }
    Ok(numbers)
}
