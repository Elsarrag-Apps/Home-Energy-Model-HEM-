from pathlib import Path

path = Path("ui/pages/10_Run_HEM_Results.py")
text = path.read_text(encoding="utf-8")

old = '''                    with profile_tabs[1]:
                        temp_columns = find_columns_containing(
                            detailed_df,
                            [
                                "operative temp",
                                "internal air temp",
                                "space heat demand",
                                "space cool demand",
                                "solar gains",
                                "internal gains",
                            ],
                        )

                        if temp_columns:
                            temp_df = detailed_df[["Timestep"] + temp_columns].set_index("Timestep")
                            st.line_chart(temp_df)
                        else:
                            st.info("No zone temperature or gain columns found.")
'''

new = '''                    with profile_tabs[1]:
                        st.markdown("#### Zone temperatures")
                        temperature_columns = find_columns_containing(
                            detailed_df,
                            [
                                "operative temp",
                                "internal air temp",
                            ],
                        )

                        if temperature_columns:
                            temperature_df = detailed_df[
                                ["Timestep"] + temperature_columns
                            ].set_index("Timestep")
                            st.line_chart(temperature_df)
                        else:
                            st.info("No zone temperature columns found.")

                        st.markdown("#### Zone gains")
                        gain_columns = find_columns_containing(
                            detailed_df,
                            [
                                "solar gains",
                                "internal gains",
                            ],
                        )

                        if gain_columns:
                            gains_df = detailed_df[
                                ["Timestep"] + gain_columns
                            ].set_index("Timestep")
                            st.line_chart(gains_df)
                        else:
                            st.info("No zone gain columns found.")

                        st.markdown("#### Space heating / cooling demand")
                        demand_columns = find_columns_containing(
                            detailed_df,
                            [
                                "space heat demand",
                                "space cool demand",
                            ],
                        )

                        if demand_columns:
                            demand_df = detailed_df[
                                ["Timestep"] + demand_columns
                            ].set_index("Timestep")
                            st.line_chart(demand_df)
                        else:
                            st.info("No heating/cooling demand columns found.")
'''

if old not in text:
    raise RuntimeError("Could not find the zone temperature chart block to replace.")

text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("Split zone results into separate temperature, gains and demand charts.")