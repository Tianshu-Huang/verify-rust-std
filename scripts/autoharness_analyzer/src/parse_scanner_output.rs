use anyhow::bail;
use anyhow::Result;
use serde::Deserialize;
use std::collections::HashMap;
use std::fs::File;
use std::io::BufRead;
use std::io::BufReader;
use std::path::Path;

// Parse the CSV files that the Kani `scanner` tool outputs
// and store which functions are safe and unsafe

// Number of columns in {crate_name}_scan_functions.csv.
const SCANNER_COLS: usize = 6;

/// Single row of data in {crate_name}_scan_functions.csv
#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct ScanFnsRow {
    pub name: String,
    pub is_unsafe: bool,
    pub has_unsafe_ops: bool,
    has_unsupported_input: bool,
    has_loop_or_iterator: bool,
}

pub fn process_scan_fns(file_path: &Path, krate: &str) -> Result<HashMap<String, ScanFnsRow>> {
    let file = File::open(file_path).unwrap_or_else(|_| panic!("Cannot open file {:?}", file_path));
    let reader = BufReader::new(file);
    let mut fn_to_row_data = HashMap::new();

    for (index, line) in reader.lines().enumerate().skip(1) {
        let line = line?;

        // The entries are split by semicolons, but we can't just split by that since the function names can also include semicolons
        // e.g. the row "ptr::mut_ptr::<impl *mut [T; N]>::as_mut_ptr";false;false;true;false.
        // So split by ;true or ;false instead--whichever comes first--then take everything before the match as the function name
        let true_index = line.find(";true");
        let false_index = line.find(";false");

        let split_index = match (true_index, false_index) {
            (Some(t), Some(f)) => t.min(f),
            (Some(t), None) => t,
            (None, Some(f)) => f,
            (None, None) => bail!("Invalid format in line {}: {}", index + 1, line),
        };

        let (name, rest) = line.split_at(split_index);
        let mut fields = vec![name];
        // Now that we've found the function name, the rest is just booleans, so we can split by ; to get the rest
        fields.extend(rest[1..].split(';'));

        let name = strip_crate_prefix(name, krate);
        fields[0] = &name;
        parse_row(&mut fn_to_row_data, fields, index + 1)?;
    }

    Ok(fn_to_row_data)
}

// Backfill only: copy of Kani's `kani_metadata::strip_crate_prefix` (model-checking/kani#4903).
fn strip_crate_prefix(name: &str, krate: &str) -> String {
    let needle = format!("{krate}::");
    if !name.contains(&needle) {
        return name.to_string();
    }
    let mut out = String::with_capacity(name.len());
    let mut rest = name;
    // The previous char in the input, used to decide whether a `<crate>::` here
    // is a crate-root *qualifier* (droppable) or a path *continuation* segment
    // (a module/item that happens to share the crate's name, which must be
    // kept). A qualifier appears at the start or after a type/path delimiter
    // (`<`, `,`, ` `, `&`, `*`, `(`, `[`, ...); a continuation appears after
    // `::`. So drop `<crate>::` only when the previous char is neither part of
    // an identifier nor `:`. After dropping, pretend the previous char is `:`
    // so an immediately following same-named segment is treated as a
    // continuation (e.g. `main::main::{closure#0}` -> `main::{closure#0}`).
    let mut prev: Option<char> = None;
    loop {
        let at_qualifier = match prev {
            None => true,
            Some(c) => !c.is_alphanumeric() && c != '_' && c != ':',
        };
        if at_qualifier && rest.starts_with(&needle) {
            rest = &rest[needle.len()..];
            prev = Some(':');
            continue;
        }
        let Some(ch) = rest.chars().next() else { break };
        out.push(ch);
        prev = Some(ch);
        rest = &rest[ch.len_utf8()..];
    }
    out
}

fn parse_row(
    rows: &mut HashMap<String, ScanFnsRow>,
    fields: Vec<&str>,
    line_number: usize,
) -> Result<()> {
    if fields.len() != SCANNER_COLS {
        bail!(
            "Expected {} fields, got {} in line {}. Fields: {:?}",
            SCANNER_COLS,
            fields.len(),
            line_number,
            fields
        );
    }

    let fn_name = fields[0].to_string();
    rows.insert(
        fn_name.clone(),
        ScanFnsRow {
            name: fn_name,
            is_unsafe: fields[1].parse().unwrap_or(false),
            has_unsafe_ops: fields[2].parse().unwrap_or(false),
            has_unsupported_input: fields[3].parse().unwrap_or(false),
            has_loop_or_iterator: fields[4].parse().unwrap_or(false),
        },
    );

    Ok(())
}
